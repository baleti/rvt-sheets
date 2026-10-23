"""p11_probe.py FILE : per schedule view: grand total flags, sort grouping flags, itemize flag (all keys with 'tem' or 'otal'), count of fields with totals"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.reader import ob
d = Decoder(sys.argv[1]); doc = d.doc()
for vid, v in doc['views'].items():
    if v.get('kind') != 'schedule': continue
    r = d.f.rec(vid, 'DBViewSchedule')
    if not r: continue
    sch = ob(r['fields'].get('m_pSchema')) or {}
    flags = {k: sch[k] for k in sch if ('tem' in k or 'otal' in k) and not isinstance(sch[k], (list, dict))}
    grp = [(ob(s) or {}).get('m_groupingFlags') for s in sch.get('m_sortFieldArr') or []]
    print('P', vid, v.get('name'), flags, 'grouping', grp, 'itemize', r['fields'].get('m_bItemizeEveryInstance'), [k for k in r['fields'] if 'tem' in k])
