"""undrawn.py FILE VIEWID: listed elements of the view that produced no primitive in our draw, by class / category / name (candidates for 'Revit draws it, we don't')"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); vid = int(sys.argv[2])
dr = vd.draw(vid)
prims = dr['prims'] if isinstance(dr, dict) else getattr(dr, 'prims', None)
if prims is None: print(type(dr), getattr(dr, 'keys', lambda: dir(dr))()); sys.exit()
drawn = {p.get('elem') for p in prims}
I = vd.vis.info.info; c = collections.defaultdict(list)
for e in vd.vis.elements(vid):
    if e in drawn: continue
    i = I.get(e, {}); r = dec.f.rec(e) or {}
    c[(i.get('cls'), i.get('cat'), (doc['categories'].get(i.get('cat')) or {}).get('name'))].append(e)
for k, v in sorted(c.items(), key=lambda kv: -len(kv[1])): print(k, len(v), v[:6])
