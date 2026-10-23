"""curtain_probe.py FILE VIEWID [cat:CATID] : listed elements of a category (default curtain mullions / panels / grid lines): class, drawn prim count, bbox"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); vid = int(sys.argv[2])
cats = {int(sys.argv[3][4:])} if len(sys.argv) > 3 and sys.argv[3].startswith('cat:') else {-2000171, -2000170, -2000321}
dr = ViewDrawer(dec, doc).draw(vid)
drawn = collections.Counter(p.get('elem') for p in dr['prims'])
for i in vis.elements(vid):
    e = vis.info.info.get(i, {})
    if e.get('cat') not in cats: continue
    bb = vis.info.bbox(i); bb = None if bb is None else [round(float(v), 1) for r in bb for v in r]
    print(i, e.get('cls'), e.get('cat'), 'drawn', drawn.get(i, 0), 'bbox', bb)
