"""plant_probe.py FILE VIEWID EID... : walk_record curves of planting instances (count, flags histogram, gs) and their symbol ids."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
import rvtsheets.viewdraw as VD
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); vid = int(sys.argv[2])
W = {int(x) for x in sys.argv[3:]}
orig = VD.Walker.walk_record
def wr(self, eid, *a, **k):
    r = orig(self, eid, *a, **k)
    if eid in W:
        cs = r['curves']
        print(eid, 'type', vd.vis.info.info[eid].get('type'), 'fam', vd.vis.info.info[eid].get('fam'), 'detail ctx', self.ctx.detail, 'ncurves', len(cs))
        print('  flags', collections.Counter(hex(c.get('flags') or 0) for c in cs).most_common(8), 'npts', collections.Counter(len(c['pts']) for c in cs if 'pts' in c).most_common(5))
        print('  ctrl', [(kk, vv) for kk, vv in (dec.f.rec(eid)['fields'] or {}).items() if 'ymbol' in kk or 'ype' in kk][:5])
    return r
VD.Walker.walk_record = wr
dr = vd.draw(vid)
print({k: v for k, v in dr['stats'].items() if isinstance(v, (int, float)) and v})
