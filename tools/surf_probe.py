"""surf_probe.py FILE VID : RVT_DBG_SURF output of the view's draw + the listed walls with their materials' surface patterns (which wall faces should get a surface hatch)"""
import sys, os
os.environ['RVT_DBG_SURF'] = '1'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); vid = int(sys.argv[2])
dr = vd.draw(vid); prims = dr['prims'] if isinstance(dr, dict) else dr.prims
hatched = {p.get('elem') for p in prims if p.get('layer') == 'surface_fill'}
mats = vd.materials()
for e in vd.vis.elements(vid):
    i = vd.vis.info.info[e]
    if i['cls'] not in ('SWall', 'Wall', 'WallSweep', 'Floor', 'ProfileRoof', 'Roof', 'FamilyInstance'): continue
    bb = vd.vis.info.bbox(e)
    ms = sorted({m for m in (vd.elem_materials(e) if hasattr(vd, 'elem_materials') else [])})
    print(i['cls'], e, 'hatched' if e in hatched else '-', None if bb is None else [[round(float(x), 1) for x in r] for r in bb], ms)
