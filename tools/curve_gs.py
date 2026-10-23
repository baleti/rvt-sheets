"""curve_gs.py FILE VIEWID EID : walker curves of an element with graphic style id / category / name, flags, points (what a symbolic line is made of)"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
import rvtsheets.viewdraw as VD
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); W = int(sys.argv[3])
orig = VD.Walker.walk_record
def wr(self, eid, *a, **k):
    r = orig(self, eid, *a, **k)
    if eid == W:
        for c in r['curves']:
            gs = c.get('gs'); st = doc['gstyles'].get(gs) or {}
            pts = np.asarray(c.get('pts'), float)
            print('curve gs', gs, 'cat', st.get('cat'), 'name', (doc['categories'].get(st.get('cat')) or {}).get('name'), 'flags', hex(c.get('flags') or 0), 'n', len(pts), np.round(pts[[0, -1]], 2).tolist())
    return r
VD.Walker.walk_record = wr
vd.draw(int(sys.argv[2]))
