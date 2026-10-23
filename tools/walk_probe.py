"""walk_probe.py FILE VIEWID EID... : view stats of walk errors and, per element, what Walker.walk_record returns (piece key sizes) with the view's context."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); vid = int(sys.argv[2])
dr = vd.draw(vid)
print({k: v for k, v in dr['stats'].items() if 'err' in k or 'skip' in k or 'hidden' in k})
import rvtsheets.viewdraw as VD
orig = VD.Walker.walk_record
def wr(self, eid, *a, **k):
    r = orig(self, eid, *a, **k)
    if eid in WATCH:
        print('walk', eid, {kk: (len(vv) if hasattr(vv, '__len__') else vv) for kk, vv in r.items()})
    return r
WATCH = {int(x) for x in sys.argv[3:]}
VD.Walker.walk_record = wr
vd2 = ViewDrawer(dec, doc); vd2.draw(vid)
print('cat names', {c: (doc['categories'].get(c) or {}).get('name') for c in (-2001160, -2001360, -2001120)})
v = doc['views'][vid]
print('view keys', [k for k in v.keys()][:40])
print('crop', v.get('crop'), v.get('crop_box'), v.get('cropbox'))
for e in sorted(WATCH):
    print(e, 'bbox', vd.vis.info.bbox(e))
