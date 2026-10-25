"""p17_probe.py FILE VID : listed Floor / Roof / Ceiling elements of the view with bbox z and prim counts (what could occlude framing below)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); vid = int(sys.argv[2])
dr = vd.draw(vid); prims = dr['prims'] if isinstance(dr, dict) else dr.prims
cnt = collections.Counter((p.get('elem'), p.get('layer')) for p in prims)
for e in vd.vis.elements(vid):
    i = vd.vis.info.info[e]
    if i['cls'] in ('Floor', 'Roof', 'ProfileRoof', 'Ceiling', 'FootPrintRoof', 'SlabEdge'):
        bb = vd.vis.info.bbox(e); print('P', i['cls'], e, None if bb is None else [[round(float(x), 1) for x in r] for r in bb], {k[1]: n for k, n in cnt.items() if k[0] == e})
