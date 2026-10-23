"""p8_probe.py FILE : every schedule view with its m_filterArr (raw) and field headings"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); doc = d.doc()
for vid, v in doc['views'].items():
    if v.get('kind') != 'schedule': continue
    r = d.f.rec(vid); f = r['fields']
    sch = f.get('m_pSchema'); sch = sch['obj'] if isinstance(sch, dict) and 'obj' in sch else sch
    if not sch: continue
    print('P', vid, v.get('name'), 'filters:', str(sch.get('m_filterArr'))[:700])
