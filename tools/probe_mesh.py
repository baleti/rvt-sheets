"""probe_mesh.py FILE EID : triangle statistics of rvt_elemmesh.element_mesh(EID) as shaded3d sees it (area by dominant normal, bbox, triangle count)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
import rvt_elemmesh as E
dec = Decoder(sys.argv[1]); doc = dec.doc(); f = dec.f
for eid in map(int, sys.argv[2:]):
    m = E.element_mesh(f.g, eid); T = np.asarray(m.get('tris') or [], float).reshape(-1, 3, 3)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); a = np.linalg.norm(n, axis=1) / 2; n = n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    print(eid, 'tris', len(T), 'area %.2f' % a.sum(), 'bbox', T.reshape(-1, 3).min(0).round(2), T.reshape(-1, 3).max(0).round(2), 'mat', m.get('mat'))
    key = np.round(n, 1)
    for k in np.unique(key, axis=0):
        s = (key == k).all(1); print('   normal', k, 'tris', s.sum(), 'area %.2f' % a[s].sum(), 'largest tri %.3f' % a[s].max())
