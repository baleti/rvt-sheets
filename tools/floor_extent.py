"""floor_extent.py FILE EID... : stored header bbox vs reader mesh bbox of elements (is the stored bbox under-reporting the solid extent?)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
import rvt_elemmesh as E_
dec = Decoder(sys.argv[1]); f = dec.f
for eid in map(int, sys.argv[2:]):
    h = f.eh.get(eid) or {}
    try:
        T = np.asarray(E_.element_mesh(f.g, eid).get('tris') or [], float).reshape(-1, 3)
        mb = (T.min(0).round(2).tolist(), T.max(0).round(2).tolist()) if len(T) else None
    except Exception as ex: mb = repr(ex)[:80]
    print(eid, 'hdr bbox', {k: h.get(k) for k in ('m_bbox', 'm_boundingBox') if k in h} or list(h)[:8], 'mesh bbox', mb, flush=True)
