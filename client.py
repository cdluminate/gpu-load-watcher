'''
Send JSON GPU usage to server.py instance.
Copyright (C) 2023, Mo Zhou <lumin@debian.org>
MIT/Expat License

Usage
=====

At the client side:
$ python3 client.py --server-url=http://<server_name>:<port>/submit
'''
import re
import os
import sys
import subprocess
import argparse
import socket
import rich
from collections import defaultdict
import gpustat
import requests
import time
console = rich.get_console()


def gpustat_filtered() -> object:
    '''
    return json-serializable gpustat results
    '''
    # make a new query
    stat = gpustat.new_query().jsonify()
    # reformat time
    stat['query_time'] = stat['query_time'].timestamp()
    # filter the query to include only information we want
    for gpu in stat['gpus']:
        # filter some information
        for k in ('uuid', 'fan.speed', 'utilization.enc',
                  'utilization.dec', 'power.draw', 'enforced.power.limit',
                  'temperature.gpu'):
            if k in gpu:
                gpu.pop(k)
        # convert per-process stat into per-user stat
        users = defaultdict(int)
        for p in gpu['processes']:
            users[p['username']] += p['gpu_memory_usage']
        gpu.pop('processes')
        gpu['users'] = dict(users)
    # should be safe to use
    return stat


def client_loop(args):
    '''
    infinite loop for client side
    '''
    while True:
        s = gpustat_filtered()
        try:
            r = requests.post(ag.server_url, json=s)
            console.print(r.status_code, r.json())
        except requests.ConnectionError:
            console.print(time.time(), 'connection error')
        time.sleep(args.interval)


if __name__ == '__main__':
    ag = argparse.ArgumentParser()
    ag.add_argument('--server-url', type=str, default='')
    ag.add_argument('--hostname', type=str, default=socket.gethostname())
    ag.add_argument('--interval', type=int, default=5)
    ag = ag.parse_args()
    console.print(ag)

    if not ag.server_url:
        s = gpustat_filtered()
        console.print('[violet on white]>_< Server URL not specified. Printing only.')
        console.print(s)
    else:
        client_loop(ag)
