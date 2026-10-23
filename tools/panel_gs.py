"""panel_gs.py FILE VIEWID EID... : per solid of the element's walk_record: graphic style id, its category, drawable_gs, point/tri counts"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
import rvtsheets.viewdraw as VD
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); vid = int(sys.argv[2]); WATCH = {int(x) for x in sys.argv[3:]}
orig = VD.Walker.walk_record
def wr(self, eid, *a, **k):
    r = orig(self, eid, *a, **k)
    if eid in WATCH:
        for s in r['solids']:
            gs = s.get('gs'); st = doc['gstyles'].get(gs) or {}
            print(eid, 'solid gs', gs, 'cat', st.get('cat'), 'name', st.get('name'), 'drawable', vd.drawable_gs(gs), 'keys', sorted(s)[:8])
    return r
VD.Walker.walk_record = wr
vd.draw(vid)
