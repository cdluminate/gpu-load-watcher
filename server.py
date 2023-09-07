'''
Receive and Serve JSON GPU usage to from client.py instances.
Copyright (C) 2023, Mo Zhou <lumin@debian.org>
MIT/Expat License

Usage
=====

At the server side: `$ python3 server.py`
'''
import gc
import time
import argparse
import datetime
import rich
console = rich.get_console()
from flask import Flask, request
app = Flask(__name__)

HEADER = '''
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="5" />
    <title>Mo's GPU Watcher</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-4bw+/aepP/YC94hEpVNVgiZdgIC5+VKNBQNGCHeKRQN+PtmoHDEXuppvnDJzQIu9" crossorigin="anonymous">
  </head>
  <body>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/js/bootstrap.bundle.min.js" integrity="sha384-HwwvtgBNo3bZJJLYd8oVXjrBZt8cqVSpeBNS5n7C8IVInixGAoxmnlMuBnhbgrkm" crossorigin="anonymous"></script>
    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.11.8/dist/umd/popper.min.js" integrity="sha384-I7E8VVD/ismYTF4hNIPjVp/Zjvgyol6VFvRkX/vR+Vc4jQkC+hVqc2pM8ODewa9r" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/js/bootstrap.min.js" integrity="sha384-Rx+T1VzGupg4BHQYs2gCW9It+akI2MM/mndMCy36UVfodzcJcF0GGLxZIzObiEfa" crossorigin="anonymous"></script>
'''

TAIL = '''
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


@app.route('/')
def root():
    body = '''<br><div class='container'>'''
    for hostname in sorted(__G__.keys()):
        body += html_per_host(__G__[hostname], __G_lastsync__[hostname])
    body += '''</div>'''
    return HEADER + body + TAIL


@app.route('/submit', methods=['POST'])
def submit():
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
