"""elem_geom.py FILE.rvt EID VIEWID : bbox of the element vs the view's range / crop volume (why 'outside_view_volume')"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); eid = int(sys.argv[2])
for vid in map(int, sys.argv[3:]):
    v = vis.effective(doc['views'][vid]); bb = vis.info.bbox(eid)
    print(eid, vis.info.info[eid]['cls'], 'bbox', bb.round(2).tolist(), 'view', vid, v['name'], 'range', {k: (round(x, 2) if isinstance(x, float) else x) for k, x in (v.get('range') or {}).items()}, 'crop_active', (v.get('crop') or {}).get('crop_active'), 'vol', vis.volume(v)(bb))
    c = v.get('crop') or {}
    if c.get('basis'):
        import numpy as np, itertools
        cs = np.array([[bb[i][0], bb[j][1], bb[k][2]] for i, j, k in itertools.product((0, 1), repeat=3)]); loc = (cs - np.asarray(c['origin'], float)) @ np.asarray(c['basis'], float).T
        print('   crop-frame min', loc.min(0).round(2).tolist(), 'max', loc.max(0).round(2).tolist(), 'bounds', [[round(x, 2) for x in b] for b in c['bounds']], 'active', c.get('active'), 'far_clip_active', c.get('far_clip_active'))
