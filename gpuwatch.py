#!/usr/bin/env python3
'''
Utility to record GPU usage of the deep learning server/workstation.
Copyright (C) 2020 Mo Zhou <lumin@debian.org>
License: MIT/Expat

Configuration:
    (1) append one the following line to /etc/crontab
```
* * * * * lumin cd && python3 gpuwatch.py snapshot
* * * * * lumin cd && /home/lumin/anaconda3/bin/python3 gpuwatch.py snapshot
```
'''
import os
import sys
import json
import argparse
import time
import subprocess
import glob
import collections
import re
from termcolor import cprint, colored
import json
import sqlite3
import statistics


__DB__ = '/var/log/__gpuwatch__.db' if os.getuid() == 0 else '__gpuwatch__.db'
if not os.path.exists(__DB__):
    conn = sqlite3.connect(__DB__)
    c = conn.cursor()
    c.execute('''CREATE TABLE userwatch (time real, name text, processes inteter, vmem_occupy real)''')
    c.execute('''CREATE TABLE gpuwatch (time real, gpu_util real, vmem_ratio real)''')
    conn.commit()
    conn.close()


def main_snapshot(argv):
    '''
    Record the current gpustat data into the database
    '''
    ag = argparse.ArgumentParser()
    ag.add_argument('-B', '--db', type=str, default=__DB__)
    ag = ag.parse_args(argv)

    stamp = time.time()
    gpustat = subprocess.Popen(['gpustat'], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE).communicate()[0].decode().strip()

    names = re.findall(r'(\w+)\(\d+M\)', gpustat)
    counter = collections.Counter(names)
    vram_used, vram_total = tuple(zip(*re.findall(r'(\d+)\s/\s(\d+)\s.B', gpustat)))
    vram_ratio = sum(int(x) for x in vram_used) / sum(int(x) for x in vram_total)
    gpu_util = statistics.mean(int(x) for x in re.findall(r'(\d+)\s%', gpustat))
    vram_occupy = {user: sum(int(x) for x in re.findall(rf'{user}\((\d+)\w\)',
        gpustat)) / sum(int(x) for x in vram_total) for user in counter.keys()}

    conn = sqlite3.connect(ag.db)
    c = conn.cursor()
    for (k, v) in counter.items():
        c.execute(f'''INSERT INTO userwatch VALUES ({stamp}, "{k}", {v}, {vram_occupy[k]})''')
    c.execute(f'''INSERT INTO gpuwatch VALUES ({stamp}, {gpu_util}, {vram_ratio})''')
    conn.commit()
    conn.close()


def main_stat(argv):
    '''
    Print statistics by inspecting the database
    '''
    ag = argparse.ArgumentParser()
    ag.add_argument('-B', '--db', type=str, default=__DB__)
    ag.add_argument('-s', '--span', type=str, default='day',
            choices=('hour', 'day', 'week', 'month', 'season'))
    ag.add_argument('--plot', action='store_true')
    ag.add_argument('--no_user', action='store_true')
    ag.add_argument('--no_system', action='store_true')
    ag = ag.parse_args(argv)
    # Connect to database
    conn = sqlite3.connect(ag.db)
    c = conn.cursor()
    stamp_lower = time.time() - {'hour': 3600, 'day': 3600*24, 'week': 3600*24*7,
            'month': 3600*24*30, 'season': 3600*24*90}[ag.span]
    # Query the database : userwatch
    gpuwatch = collections.defaultdict(list)
    stamps = list()
    for row in c.execute(f'''SELECT * FROM gpuwatch WHERE time > {stamp_lower}'''):
        stamp, gpu_util, vram_ratio = row
        stamps.append(float(stamp))
        gpuwatch['gpu_util'].append(gpu_util)
        gpuwatch['vram_ratio'].append(vram_ratio)
    # Query the database : gpuwatch
    userstat = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in c.execute(f'''SELECT * FROM userwatch WHERE time > {stamp_lower}'''):
        stamp, user, processes, vram_occupy = row
        userstat[user]['cumtime'].append(1)
        userstat[user]['processes'].append(processes)
        userstat[user]['vram_occupy'].append(vram_occupy)
    # Printing
    cprint(f':: GPU Usage Statistics (in the past {ag.span})', 'yellow')
    if not ag.no_system:
        cprint('SYSTEM |'.rjust(16), 'red', end=' ')
        for (k, v) in gpuwatch.items():
            print(f'{k}=', colored(str('%7.2f'%statistics.mean(v)), 'cyan'), end=' ')
        print()
    if not ag.no_user:
        for (k, v) in userstat.items():
            cprint(f'{k} |'.rjust(16), 'blue', end=' ')
            for attr in sorted(v.keys()):
                if attr == 'cumtime':
                    print(f'{attr}=', colored(str('%8.2f'%sum(v[attr])), 'cyan'), end=' ')
                else:
                    print(f'{attr}=', colored(str('%8.2f'%statistics.mean(v[attr])), 'cyan'), end=' ')
            print()
    # [optional] Plotting
    if ag.plot:
        import pylab as lab
        import numpy as np
        date_fmt = '%y-%m-%d %H:%M:%S'
        date_formatter = lab.matplotlib.dates.DateFormatter(date_fmt)
        # offset the timezone to UTC+8
        stamps = [x + 3600*8 for x in stamps]

        fig, ax = lab.subplots()
        a = [float(x) for x in gpuwatch['gpu_util']]
        b = [float(x) for x in gpuwatch['vram_ratio']]
        t = lab.matplotlib.dates.epoch2num(stamps)

        ax.plot_date(t, a, 'r.-')
        ax.set(ylim=(0., 100.))
        ax.grid(True)
        ax.legend(['gpu_util'], loc='lower left')
        ax.xaxis.set_major_formatter(date_formatter)

        ax2 = ax.twinx()
        ax2.plot_date(t, b, 'b.-')
        ax2.set(ylim=(0., 1.))
        ax2.grid(True)
        ax2.legend(['vram_ratio'], loc='lower right')
        ax2.xaxis.set_major_formatter(date_formatter)

        fig.autofmt_xdate()
        lab.savefig('gpuwatch.svg')


if __name__ == '__main__':
    eval(f'main_{sys.argv[1]}')(sys.argv[2:])
