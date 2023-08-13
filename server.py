'''
Receive and Serve JSON GPU usage to from client.py instances.
Copyright (C) 2023, Mo Zhou <lumin@debian.org>
MIT/Expat License
'''
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
'''

TAIL = '''
  </body>
</html>
'''

G_latest = dict()

def html_per_gpu(gpu) -> str:
    memory_percent = int(100 * (gpu['memory.used'] / float(gpu['memory.total'])))
    users=' '.join(['{a} ({b}M)'.format(a=a, b=b) for (a, b) in gpu['users'].items()])
    html = '''
<li class="list-group-item">
<div class='hstack gap-3'>

<div><h4 class='lead p-2'>{index}: {name}</h4></div>

<div class="lead p-2 progress w-25" role="progressbar" aria-label="Utilization" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
<div class="progress-bar overflow-visible text-dark text-center" style="width: {utilization_gpu}%"><b>Utilization: {utilization_gpu}%</b></div>
</div>

<div class="lead p-2 progress w-25" role="progressbar" aria-label="Memory" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
<div class="progress-bar overflow-visible text-dark text-center" style="width: {percent}%"><b>{percent}% ({memory_used}M / {memory_total}M)</b></div>
</div>

<small><b>Users:</b> {users}</small>
<small><b>PastWeek:</b> WIP</small>

</div><!-- hstack -->

</li>'''.format(
        index=gpu['index'],
        name=gpu['name'],
        utilization_gpu=gpu['utilization.gpu'],
        percent=memory_percent,
        memory_used=gpu['memory.used'],
        memory_total=gpu['memory.total'],
        users=users,
        )
    return html

def html_per_host(host) -> str:
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
    for hostname in sorted(G_latest.keys()):
        body += html_per_host(G_latest[hostname])
    #for hostname in sorted(G_latest.keys()):
    #    body += html_per_host(G_latest[hostname])
    body += '''</div>'''
    return HEADER + body + TAIL

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    G_latest[data['hostname']] = data
    return data
