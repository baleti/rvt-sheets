"""occ_probe.py FILE VIEWID X Y : floors/roofs/ceilings (underlay occluder candidates) of a plan whose plan-space mesh contains world point (X, Y): id, class, category, z range."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from shapely.geometry import Polygon, Point
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
import rvt_elemmesh as E
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc); vid = int(sys.argv[2])
pt = Point(float(sys.argv[3]), float(sys.argv[4]))
v = doc['views'][vid]; print('range', v.get('range'))
for e in vd.vis.elements(vid):
    inf = vd.vis.info.info.get(e) or {}
    if inf.get('cat') not in (-2000032, -2000035, -2000038): continue
    bb = vd.vis.info.bbox(e)
    try: T = np.asarray(E.element_mesh(vd.f.g, e).get('tris') or [], float).reshape(-1, 3, 3)
    except Exception as ex: print(e, 'mesh error', ex); continue
    hit = any(Polygon(t[:, :2]).is_valid and Polygon(t[:, :2]).buffer(0.01).contains(pt) for t in T)
    print(e, inf.get('cls'), inf.get('cat'), 'z', None if bb is None else (round(bb[0][2], 2), round(bb[1][2], 2)), 'xy', None if bb is None else np.round(np.r_[bb[0][:2], bb[1][:2]], 1).tolist(), 'CONTAINS' if hit else '')
