#!/usr/bin/env python3
"""oracle_expone.py YEAR FILE TAG VIEW REGEN(0/1) [MOD]: run oracle/expone.cs (single view DXF + PNG, optional forced regeneration) in the overlay VM; results ~/rvt-research/gt_views/<year>_<tag>/ ; enqueue via write-lab/pipeline/enqueue.sh"""
import sys, os, zipfile
WL = os.path.expanduser('~/rvt-research/write-lab'); sys.path.insert(0, WL + '/campaign')
import guest
year, f, tag, view, regen = int(sys.argv[1]), os.path.abspath(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
mod = sys.argv[6] if len(sys.argv) > 6 else 'none'; ids = sys.argv[7] if len(sys.argv) > 7 else ''
OUT = os.path.expanduser('~/rvt-research/gt_views'); base = os.path.basename(f)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'oracle', 'expone.cs')).read()
cs = src.replace('__FILE__', 'C:/wl/' + tag + '_' + base).replace('__TAG__', tag).replace('__VIEW__', view).replace('__REGEN__', regen).replace('__MOD__', mod).replace('__IDS__', ids)
with guest.vmlock():
    guest.put(f, 'C:/wl/' + tag + '_' + base); p = guest.fresh(year)
    o = guest.run_job(year, p, cs, tag, 1800); print(o[-600:])
    if 'ERROR' in o and '"kind": "compile"' in o: open('%s/%s.err' % (OUT, tag), 'w').write(o); print('compile error written')
    else:
        guest.script(r'Compress-Archive -Path "C:\wl\out\%s\*" -DestinationPath "C:\wl\out\%s.zip" -Force' % (tag, tag), 300)
        z = '/tmp/claude-1000/%s.zip' % tag; guest.get('C:/wl/out/%s.zip' % tag, z)
        d = '%s/%d_%s' % (OUT, year, tag); os.makedirs(d, exist_ok=True); zipfile.ZipFile(z).extractall(d); print('wrote', d)
