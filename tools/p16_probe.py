"""p16_probe.py FILE VID : one member id per JoistSystem listed in the view"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); vid = int(sys.argv[2])
els = list(vd.vis.elements(vid))
for e in els:
    if vd.vis.info.info[e]['cls'] == 'JoistSystem':
        ms = [m for m in els if (d.f.rec(m) or {}).get('class') == 'FamilyInstance' and d.f.eid(d.f.rec(m)['fields'].get('m_hostId')) == e]
        print('P', vid, 'system', e, 'members', len(ms), 'first', ms[:2])
