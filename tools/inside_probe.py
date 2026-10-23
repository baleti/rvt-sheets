"""inside_probe.py FILE VIEWID WALLID : elements whose bbox centre lies in the wall's bbox: class, category, drawn prim count, bbox"""
import sys, os, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); vid = int(sys.argv[2]); w = int(sys.argv[3])
dr = ViewDrawer(dec, doc).draw(vid); drawn = collections.Counter(p.get('elem') for p in dr['prims'])
b = vis.info.bbox(w); lo, hi = np.asarray(b[0]), np.asarray(b[1])
for i in vis.elements(vid):
    bb = vis.info.bbox(i)
    if bb is None: continue
    c = (np.asarray(bb[0]) + np.asarray(bb[1])) / 2
    if (c >= lo - .05).all() and (c <= hi + .05).all():
        e = vis.info.info.get(i, {}); print(i, e.get('cls'), e.get('cat'), 'drawn', drawn.get(i, 0), np.round(np.r_[bb[0], bb[1]], 1).tolist())
