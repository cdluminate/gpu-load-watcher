'''
Receive and Serve JSON GPU usage to from client.py instances.
Copyright (C) 2023, Mo Zhou <lumin@debian.org>
MIT/Expat License

Usage
=====

At the server side: `$ python3 server.py`
If you want to make this robust, just use Makefile.server to
install the systemd service unit in the user mode.
'''
import gc
import time
import argparse
import datetime
from collections import defaultdict
import gzip
import json
import rich
console = rich.get_console()
from flask import Flask, request
app = Flask(__name__)

HEADER = '''
<!--
This webpage is automatically generated by server.py from https://github.com/cdluminate/gpu-load-watcher
Copyright (C) 2023 Mo Zhou <lumin@debian.org>
License: MIT/Expat
-->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="7" />
    <title>Mo's GPU Watcher</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-T3c6CoIi6uLrA9TneNEoa7RxnatzjcDSCmG1MXxSR1GAsXEV/Dwwykc2MPK8M2HN" crossorigin="anonymous">
  </head>
  <body>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js" integrity="sha384-C6RzsynM9kWDrMNeT87bh95OGNyZPhcTNXj1NW7RuBCsyN/o0jlpcV8Qyq46cDfL" crossorigin="anonymous"></script>


<nav class="navbar navbar-expand-lg bg-body-tertiary fixed-top" style="display: block" id="navbar">
  <div class="container-fluid">
    <a class="navbar-brand" href="/">GPU Status</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarSupportedContent" aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navbarSupportedContent">
      <ul class="navbar-nav me-auto mb-2 mb-lg-0">
        <li class="nav-item dropdown">
          <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
            Scope
          </a>
          <ul class="dropdown-menu">
            <li><a class="dropdown-item" href="/">All (default)</a></li>
            <li><hr class="dropdown-divider"></li>
            @NAV_CLIENTS@
          </ul>
        </li>
        <li class="nav-item dropdown">
          <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
            Stat.
          </a>
          <ul class="dropdown-menu">
            @STAT_CLIENTS@
          </ul>
        </li>
        <li class="nav-item dropdown">
          <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
            Finder
          </a>
          <ul class="dropdown-menu">
            @FIND_CLIENTS@
          </ul>
        </li>
        <li class="nav-item dropdown">
          <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
            User
          </a>
          <ul class="dropdown-menu">
            @USER_CLIENTS@
          </ul>
        </li>
      </ul>
      <div class="nav-item">
          Source Code:
          <a href="https://github.com/cdluminate/gpu-load-watcher/blob/main/server.py"><span class="badge text-bg-primary">Server</span></a>
          <a href="https://github.com/cdluminate/gpu-load-watcher/blob/main/client.py"><span class="badge text-bg-primary">Client</span></a>
      </div>
    </div>
  </div>
</nav>
'''

TAIL = '''

<hr>
<p class="text-center text-body-tertiary">Copyright (C) 2023 Mo Zhou</p>

<!--<button onclick="foobar()">Try it</button>-->

<script>
function toggle_navbar() {
    var x = document.getElementById("navbar") ;
    if (x.style.display === "none") {
        x.style.display = "block";
    } else {
        x.style.display = "none";
    }
}

document.addEventListener('keydown',
    function(e){
        var key = e.keyCode || e.which;
        if (key == 86)
            toggle_navbar();
    })
</script>

  </body>
</html>
'''


# global dict storing the latest record from each client
__G__ = dict()
# global dict storing the timestamp of the latest record
__G_lastsync__ = dict()


def html_per_gpu(gpu) -> str:
    memory_percent = int(100 * (gpu['memory.used'] / float(gpu['memory.total'])))
    if memory_percent <= 25:
        memory_color = 'bg-success'
    elif memory_percent <= 50:
        memory_color = 'bg-info'
    elif memory_percent <= 75:
        memory_color = 'bg-warning'
    else:
        memory_color = 'bg-danger'
    if gpu['utilization.gpu'] <= 25:
        util_color = 'bg-success'
    elif gpu['utilization.gpu'] <= 50:
        util_color = 'bg-info'
    elif gpu['utilization.gpu'] <= 75:
        util_color = 'bg-warning'
    else:
        util_color = 'bg-danger'
    users=' '.join(['{a}({b}M)'.format(a=a, b=b) for (a, b) in gpu['users'].items()])
    html = '''
<li class="list-group-item">
<div class='hstack gap-3'>

<div><span>{index}: {name}</span></div>

<div class="lead progress w-25" role="progressbar" aria-label="Utilization" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
<div class="progress-bar {util_color} overflow-visible text-dark text-center" style="width: {utilization_gpu}%"><b>GPU-Util: {utilization_gpu}%</b></div>
</div>

<div class="lead progress w-25" role="progressbar" aria-label="Memory" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
<div class="progress-bar {memory_color} overflow-visible text-dark text-center" style="width: {memory_percent}%"><b>GPU-Mem: {memory_percent}% ({memory_used}M / {memory_total}M)</b></div>
</div>

<div>
<small><b>Users:</b> {users}</small>
</div>

</div><!-- hstack -->

</li>'''.format(
        index=gpu['index'],
        name=gpu['name'],
        utilization_gpu=gpu['utilization.gpu'],
        util_color=util_color,
        memory_percent=memory_percent,
        memory_color=memory_color,
        memory_used=gpu['memory.used'],
        memory_total=gpu['memory.total'],
        users=users,
        )
    return html

def html_per_host(host, lastsync) -> str:
    # calculate the time since the last sync
    since_last_sync = int(time.time() - lastsync)
    if since_last_sync > 60:
        since_last_sync = f'''<span class="badge bg-danger">Last Sync: {since_last_sync} (ERROR: Client Disconnected)</span>'''
    else:
        since_last_sync = f'''<span class="badge bg-success">Last Sync: {since_last_sync} (OK)</span>'''
    # format sysstat
    mem_percent = int(100.0 * host['vm_available_M'] / host['vm_total_M'])
    sysstat = f'''CPU: {host['cpu_percent']:.1f}% (LoadAvg: {host['loadavg'][0]:.1f}) RAM: {mem_percent}% ({int(host['vm_available_M'])} / {int(host['vm_total_M'])})'''
    # render html
    html_gpus = []
    html_gpus.append('''
<div class="card">
<div class="card-header">
    {hostname}
    <span>| {sysstat}</span>
    <span class="float-end">{since_last_sync}</span>
</div>
<ul class="list-group list-group-flush">
'''.format(
    hostname=host['hostname'],
    sysstat=sysstat,
    since_last_sync=since_last_sync,
))
    for gpu in host['gpus']:
        html_gpus.append(html_per_gpu(gpu))
    #for gpu in host['gpus']:
    #    html_gpus.append(html_per_gpu(gpu))
    #for gpu in host['gpus']:
    #    html_gpus.append(html_per_gpu(gpu))
    #for gpu in host['gpus']:
    #    html_gpus.append(html_per_gpu(gpu))
    html_gpus.append('''
</ul>
</div><!-- card -->
<br>
''')
    return '\n'.join(str(x) for x in html_gpus)


def gen_client_list() -> str:
    '''
    generate the client list for the navbar
    '''
    lines = []
    for client in sorted(__G__.keys()):
        lastsync = int(time.time() - __G_lastsync__[client])
        if lastsync <= 60:
            lines.append(f'<li><a class="dropdown-item" href="/{client}"><b>{client}</b>: Last Sync <span class="badge text-bg-success">{lastsync}</span>s ago</a></li>')
        else:
            lines.append(f'<li><a class="dropdown-item" href="/{client}"><b>{client}</b>: Last Sync <span class="badge text-bg-danger">{lastsync}</span>s ago</a></li>')
    return '\n'.join(lines)


def __is_low_util(gpu) -> bool:
    '''
    helper function to determine whether this GPU is free or not
    '''
    __IGNORED_USERS__ = ['gdm3', 'gdm']
    users = set(gpu['users'].keys())
    for ignored in __IGNORED_USERS__:
        if ignored in users:
            users -= {ignored,}
    return len(users) == 0 \
        or gpu['utilization.gpu'] <= 2 \
        and gpu['memory.used']/gpu['memory.total'] < 0.02


def gen_client_statistics() -> str:
    '''
    generate the client statistics for the navbar
    '''
    gpu_all, gpu_free = defaultdict(int), defaultdict(int)
    gpu_used = defaultdict(int)
    for client in __G__.keys():
        for gpu in __G__[client]['gpus']:
            index = gpu['index']
            name = gpu['name']
            gpu_all[name] += 1
            if __is_low_util(gpu):
                gpu_free[name] += 1
            else:
                gpu_used[name] += 1
    lines = []
    total_all = sum(gpu_all.values())
    lines.append(f'<li><a class="dropdown-item" href="#"><b>Total: {total_all}</b></a></li>')
    for (k, v) in gpu_all.items():
        lines.append(f'<li><a class="dropdown-item" href="#">{k}: <span class="badge text-bg-secondary">{v}</span></a></li>')
    lines.append('''<li><hr class="dropdown-divider"></li>''')
    #
    total_free = sum(gpu_free.values())
    lines.append(f'<li><a class="dropdown-item" href="#"><b>Free: {total_free}</b></a></li>')
    for (k, v) in gpu_free.items():
        lines.append(f'<li><a class="dropdown-item" href="#">{k}: <span class="badge text-bg-success">{v}</span></a></li>')
    lines.append('''<li><hr class="dropdown-divider"></li>''')
    #
    total_used = sum(gpu_used.values())
    lines.append(f'<li><a class="dropdown-item" href="#"><b>Used: {total_used}</b></a></li>')
    for (k, v) in gpu_used.items():
        lines.append(f'<li><a class="dropdown-item" href="#">{k}: <span class="badge text-bg-danger">{v}</span></a></li>')
    return '\n'.join(lines)


def gen_client_find() -> str:
    '''
    find free GPUs from all clients
    '''
    finder = defaultdict(lambda: defaultdict(int))
    for client in __G__.keys():
        for gpu in __G__[client]['gpus']:
            name = gpu['name']
            if __is_low_util(gpu):
                finder[name][client] += 1
    lines = []
    for i, name in enumerate(finder.keys()):
        lines.append(f'<li><a class="dropdown-item" href="#"><b>{name}</b></a></li>')
        for (client, number) in sorted(finder[name].items(), key=lambda x: -x[1]):
            lines.append(f'<li><a class="dropdown-item" href="/{client}">{client}: <span class="badge text-bg-success">{number}</span></a></li>')
        if i < len(finder.keys()) - 1:
            lines.append('''<li><hr class="dropdown-divider"></li>''')
    return '\n'.join(lines)


def gen_client_user_leaderboard() -> str:
    '''
    rank users across all clients based on occupied GPU tally
    '''
    def __get_users(gpu):
        __IGNORED_USERS__ = ['gdm3', 'gdm']
        users = set(gpu['users'].keys())
        for ignored in __IGNORED_USERS__:
            if ignored in users:
                users -= {ignored,}
        return users
    board = defaultdict(int)
    for client in __G__.keys():
        for gpu in __G__[client]['gpus']:
            users = __get_users(gpu)
            for user in users:
                board[user] += 1
    lines = []
    for name, occupy in sorted(board.items(), key=lambda x: -x[1]):
        lines.append(f'<li><a class="dropdown-item" href="#">{name}: <b>{occupy}</b></a></li>')
    return '\n'.join(lines)


@app.route('/')
def root():
    body = '''<br><div class='container'>'''
    for hostname in sorted(__G__.keys()):
        body += html_per_host(__G__[hostname], __G_lastsync__[hostname])
    body += '''</div>'''
    header = HEADER.replace('@NAV_CLIENTS@', gen_client_list())
    header = header.replace('@STAT_CLIENTS@', gen_client_statistics())
    header = header.replace('@FIND_CLIENTS@', gen_client_find())
    header = header.replace('@USER_CLIENTS@', gen_client_user_leaderboard())
    tail = TAIL
    return header + body + tail


@app.route('/<string:client>')
def one_client(client: str):
    body = '''<br><div class='container'>'''
    if client in __G__:
        body += html_per_host(__G__[client], __G_lastsync__[client])
    else:
        body += f'''
        <div class="alert alert-danger" role="alert">
          The specified client "{client}" does not exist.
          Check your URL and try again!
          <a href="/">Click here to reset.</a>
        </div>
        '''
    body += '''</div>'''
    header = HEADER.replace('@NAV_CLIENTS@', gen_client_list())
    header = header.replace('@STAT_CLIENTS@', gen_client_statistics())
    header = header.replace('@FIND_CLIENTS@', gen_client_find())
    header = header.replace('@USER_CLIENTS@', gen_client_user_leaderboard())
    tail = TAIL
    return header + body + tail


@app.route('/submit', methods=['POST'])
def submit():
    #print(vars(request))
    if 'Content-Type' in request.headers:
        if request.headers['Content-Type'] != 'application/json':
            console.log(f'unsupported POST content type')
            return None
    else:
        pass
    if 'Content-Encoding' in request.headers:
        if request.headers['Content-Encoding'] == 'gzip':
            data = gzip.decompress(request.data).decode()
            data = json.loads(data)
        else:
            data = request.json
    else:
        data = request.json
    __G__[data['hostname']] = data
    __G_lastsync__[data['hostname']] = time.time()
    # my cloud server does no have much memory
    gc.collect()
    return data


if __name__ == '__main__':
    ag = argparse.ArgumentParser()
    ag.add_argument('--debug', action='store_true', help='toggle debugging mode')
    ag.add_argument('-H', '--host', type=str, default='0.0.0.0')
    ag.add_argument('-P', '--port', type=int, default=4222)
    ag = ag.parse_args()

    app.run(host=ag.host, port=ag.port, debug=ag.debug)
