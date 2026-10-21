"""grid_ends.py FILE VIEWID : stored datum data of the Grid elements listed in a view (origin, axis, ends, per-view extent, bubble overrides), to decide the head end"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.reader import ob
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); f = dec.f
for eid in vis.elements(int(sys.argv[2])):
    if vis.info.info[eid]['cls'] != 'Grid': continue
    fl = f.rec(eid)['fields']
    print(eid, repr(fl.get('m_text')), {k: (round(v, 2) if isinstance(v, float) else v) for k, v in fl.items() if k in ('m_freeEnd3d', 'm_bubbleEnd3d', 'm_bubbleOverride')})
    for k in ('m_origin', 'm_xVec', 'm_yVec', 'm_Envelope', 'm_curve'):
        if fl.get(k) is not None: print('   ', k, str(fl[k])[:150])
