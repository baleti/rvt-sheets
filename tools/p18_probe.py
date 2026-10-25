"""p18_probe.py FILE VID : fraction of each JoistSystem member's plan line covered by the floors above it (the view's underlay occluder)"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from shapely.geometry import LineString
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); vid = int(sys.argv[2]); v = doc['views'][vid]
vd.draw(vid)   # builds nothing we need but warms caches
els = list(vd.vis.elements(vid)); O = np.zeros(3); Mv = np.eye(3)
tot = cov = 0; n = 0; per = {}
for e in els:
    if (d.f.rec(e) or {}).get('class') != 'FamilyInstance' or vd.vis.info.info[e]['cat'] != -2001320: continue
    bb = vd.vis.info.bbox(e)
    if bb is None: continue
    occ = vd._underlay_occluder(v, O, Mv, els, float(bb[1][2]))
    ln = LineString([(float((bb[0][0] + bb[1][0]) / 2), float(bb[0][1])), (float((bb[0][0] + bb[1][0]) / 2), float(bb[1][1]))]) if abs(bb[1][0] - bb[0][0]) < abs(bb[1][1] - bb[0][1]) else LineString([(float(bb[0][0]), float((bb[0][1] + bb[1][1]) / 2)), (float(bb[1][0]), float((bb[0][1] + bb[1][1]) / 2))])
    c = 0.0 if occ is None else ln.intersection(occ).length / max(ln.length, 1e-9)
    per[round(float(bb[1][2]), 1)] = per.get(round(float(bb[1][2]), 1), []) + [round(c, 2)]
for z, cs in sorted(per.items()): print('P', vid, 'top z', z, 'n', len(cs), 'mean covered', round(sum(cs) / len(cs), 2))
