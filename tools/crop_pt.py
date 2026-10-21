"""crop_pt.py FILE.rvt X Y Z : for every plan, crop frame position of a world point, crop_active and range (explains point-element listing)"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); p = np.array([float(a) for a in sys.argv[2:5]])
for vid, v0 in doc['views'].items():
    if v0.get('kind') != 'plan': continue
    v = vis.effective(v0); c = v.get('crop') or {}
    if not c.get('basis'): print(vid, v['name'][:24], 'no crop'); continue
    loc = (p - np.asarray(c['origin'], float)) @ np.asarray(c['basis'], float).T
    r = v.get('range') or {}
    print(vid, v['name'][:24], 'active', c.get('crop_active'), 'loc', loc.round(1).tolist(), 'bounds', [[round(x, 1) for x in b] for b in c['bounds']], 'range', r.get('bottom'), r.get('top'), 'type', r.get('plan_view_type'))
