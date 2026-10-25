#!/usr/bin/env python3
"""oracle_probe.py YEAR FILE TAG VIEWS ELEMS [SCHEDS] : run oracle/elemprobe.cs on FILE in the overlay VM (same harness as write-lab/oracle_run.py; enqueue it with
write-lab/pipeline/enqueue.sh so it takes the VM lock in turn). Results: ~/rvt-research/gt_views/<year>_<tag>.txt (+ _sched_<id>.csv exports). Compile errors: <tag>.err"""
import sys, os
WL = os.path.expanduser('~/rvt-research/write-lab'); sys.path.insert(0, WL + '/campaign')
import guest
year, f, tag, views, elems = int(sys.argv[1]), os.path.abspath(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
scheds = sys.argv[6] if len(sys.argv) > 6 else ''
OUT = os.path.expanduser('~/rvt-research/gt_views'); base = os.path.basename(f)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'oracle', 'elemprobe.cs')).read()
cs = src.replace('__FILE__', 'C:/wl/' + tag + '_' + base).replace('__TAG__', tag).replace('__VIEWS__', views).replace('__ELEMS__', elems).replace('__SCHEDS__', scheds)
with guest.vmlock():
    guest.put(f, 'C:/wl/' + tag + '_' + base); p = guest.fresh(year)
    o = guest.run_job(year, p, cs, tag, 1800); print(o[-800:])
    if 'ERROR' in o and '"kind": "compile"' in o: open('%s/%s.err' % (OUT, tag), 'w').write(o); print('compile error written')
    else:
        guest.get('C:/wl/out/%s.txt' % tag, '%s/%d_%s.txt' % (OUT, year, tag))
        for sid in [x for x in scheds.split(',') if x]: guest.get('C:/wl/out/%s_sched_%s.csv' % (tag, sid), '%s/%d_%s_sched_%s.csv' % (OUT, year, tag, sid))
        print('wrote', '%s/%d_%s.txt' % (OUT, year, tag))
