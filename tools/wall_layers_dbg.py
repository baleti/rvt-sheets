"""wall_layers_dbg.py FILE VIEWID : which cut walls go through the layer strips code (_wall_layers) and what it returns (None = drawn, False = refused), with the layer count of the wall type"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.reader import ob
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2]); vd = ViewDrawer(dec, doc)
orig = vd._wall_layers; log = []
def wrap(eid, loops, Mv, scale, res, ov, prims, st, cid=-2000011):
    n0 = len(prims); r = orig(eid, loops, Mv, scale, res, ov, prims, st, cid)
    rec = vd.f.rec(eid); t = vd.f.rec(vd.f.eid(rec['fields'].get('m_WallAttributesId'))) if cid == -2000011 and rec else None
    cs = ob((t or {}).get('fields', {}).get('m_pCompoundStructure')) if t else None
    nl = len([l for l in (cs or {}).get('m_layers') or [] if (ob(l) or {}).get('m_layerWidth', 0) > 1e-6])
    log.append((eid, cid, 'layers', nl, 'loops', len(loops), 'verts', sum(len(l) for l in loops), 'ret', r, 'prims+', len(prims) - n0)); return r
vd._wall_layers = wrap
dr = vd.draw(vid)
for x in log: print(x)
print('calls', len(log), 'stats', {k: v for k, v in dr['stats'].items() if 'layer' in k})
