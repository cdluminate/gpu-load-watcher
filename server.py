'''
Receive and Serve JSON GPU usage to from client.py instances.
Copyright (C) 2023, Mo Zhou <lumin@debian.org>
MIT/Expat License

Usage
=====

At the server side: `$ python3 server.py`
'''
import gc
import argparse
import datetime
import rich
from collections import defaultdict
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
'''

TAIL = '''
  </body>
</html>
'''

G_history = defaultdict(list)
G_history_limit : int = 512


def pastweek_stat_per_host(hostname) -> dict:
    history = G_history[hostname]
    week_all_per_gpu = dict()
    for submit in history:
        for gpu in submit['gpus']:
            gpu_index = gpu['index']
            if gpu_index not in week_all_per_gpu:
                week_all_per_gpu[gpu_index] = defaultdict(int)
            for (name, usage) in gpu['users'].items():
                week_all_per_gpu[gpu_index][name] += 1
    for index in week_all_per_gpu.keys():
        #week_all_per_gpu[index] = ' '.join(f'{k}({v})'
        week_all_per_gpu[index] = ' '.join(f'{k}'
        for (k, v) in (list(sorted(week_all_per_gpu[index].items(),
            key=lambda x: x[-1], reverse=True))[:1]))
    return week_all_per_gpu


def html_per_gpu(gpu, pastweek: dict) -> str:
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
<div class="progress-bar {util_color} overflow-visible text-dark text-center" style="width: {utilization_gpu}%"><b>Utilization: {utilization_gpu}%</b></div>
</div>

<div class="lead progress w-25" role="progressbar" aria-label="Memory" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
<div class="progress-bar {memory_color} overflow-visible text-dark text-center" style="width: {memory_percent}%"><b>{memory_percent}% ({memory_used}M / {memory_total}M)</b></div>
</div>

<small><b>Users:</b> {users}</small>
<small><b>TopUser:</b> {pastweek}</small>

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
        pastweek=pastweek[gpu['index']],
        )
    return html

def html_per_host(host, pastweek: dict) -> str:
    html_gpus = []
    html_gpus.append('''
<div class="card">
<div class="card-header">
    {hostname} -- QueryTime: {query_time}
</div>
<ul class="list-group list-group-flush">
'''.format(
    hostname=host['hostname'],
    query_time=datetime.datetime.fromtimestamp(host['query_time']),
))
    for gpu in host['gpus']:
        html_gpus.append(html_per_gpu(gpu, pastweek=pastweek))
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
    for hostname in sorted(G_history.keys()):
        pastweek = pastweek_stat_per_host(hostname)
        body += html_per_host(G_history[hostname][-1], pastweek=pastweek)
    body += '''</div>'''
    return HEADER + body + TAIL


@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    G_history[data['hostname']].append(data)
    # clean up old history (1 week time window)
    for hostname in G_history.keys():
        # get latest timestamp for host
        latest = max(x['query_time'] for x in G_history[hostname])
        week = 7 * 24 * 3600
        oldthresh = latest - week
        entries = []
        for entry in G_history[hostname]:
            if entry['query_time'] < oldthresh:
                pass
            else:
                entries.append(entry)
        if len(entries) >= G_history_limit and len(entries) % 5 == 0:
            entries = entries[::5]
        G_history[hostname] = entries
        # my cloud server does no have much memory
        gc.collect()
    return data


if __name__ == '__main__':
    ag = argparse.ArgumentParser()
    ag.add_argument('--debug', action='store_true',
        help='toggle debugging mode')
    ag.add_argument('-H', '--host', type=str, default='0.0.0.0')
    ag.add_argument('-P', '--port', type=int, default=5000)
    ag = ag.parse_args()

    app.run(host=ag.host, port=ag.port, debug=ag.debug)
