"""spot_probe.py FILE VIEWID: spot elevations of a view: stored reference z, picked element (class / id / bbox z), face z under the point WITHOUT the 1.5 ft limit (all hits), our value"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.reader import ob, INVALID
from rvtsheets import units
import rvt_elemmesh as E
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); f = dec.f
for eid in vis.elements(int(sys.argv[2])):
    if vis.info.info[eid]['cls'] != 'SpotElevation': continue
    fl = f.rec(eid)['fields']; P = np.asarray((fl.get('m_refPnts') or [[0, 0, 0]])[0], float)
    pk = ((ob(fl.get('m_pPick')) or {}).get('m_elemPicks') or [None])[0]; e = f.eid((ob(pk) or {}).get('m_elemId')) if pk else None
    cls = (f.rec(e) or {}).get('class') if e not in (None, INVALID, -1) else None
    zs = []
    if cls:
        T = np.asarray(E.element_mesh(f.g, e).get('tris') or [], float).reshape(-1, 3, 3)
        if len(T):
            n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); nl = np.linalg.norm(n, axis=1) + 1e-12; T = T[np.abs(n[:, 2]) / nl > 0.5]
            a, b, c = T[:, 0, :2], T[:, 1, :2], T[:, 2, :2]; q = P[:2]
            d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1]); ok = np.abs(d) > 1e-12; d = np.where(ok, d, 1.0)
            l1 = ((b[:, 1] - c[:, 1]) * (q[0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (q[1] - c[:, 1])) / d; l2 = ((c[:, 1] - a[:, 1]) * (q[0] - c[:, 0]) + (a[:, 0] - c[:, 0]) * (q[1] - c[:, 1])) / d
            hit = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (1 - l1 - l2 >= -1e-9)
            zs = sorted(set(round(float(x), 3) for x in (l1 * T[:, 0, 2] + l2 * T[:, 1, 2] + (1 - l1 - l2) * T[:, 2, 2])[hit]))
    print('SPOT', eid, 'stored z %.3f' % P[2], 'elem', e, cls, 'bbox', None if e is None else (vis.info.bbox(e) if e in vis.info.info else None), 'hit z', zs[:8], 'level', f.eid(fl.get('m_assocLevelId')))
