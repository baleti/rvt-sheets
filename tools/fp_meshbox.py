"""fp_meshbox.py FILE.rvt VIEWID CLASS : for TP and FP elements of CLASS in a section view, the fraction of mesh vertices inside the crop box (crop frame) vs the header-bbox verdict"""
import sys, os, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
import rvt_elemmesh as E
fn = sys.argv[1]; vid = int(sys.argv[2]); klass = sys.argv[3]; o = oracle.load(oracle.find(fn))
dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc); v = vis.effective(doc['views'][vid]); c = v['crop']
pred = set(vis.elements(vid)); G = set(o['viewelems'][vid])
Bm = np.asarray(c['basis'], float); org = np.asarray(c['origin'], float); b = c['bounds']
lo = np.array([b[i][1] for i in range(3)]); hi = np.array([b[i][0] for i in range(3)])
rows = collections.defaultdict(list)
for e in pred:
    if vis.info.info[e]['cls'] != klass: continue
    T = np.asarray(E.element_mesh(dec.f.g, e).get('tris') or [], float).reshape(-1, 3)
    if not len(T): continue
    L = (T - org) @ Bm.T
    Tr = L.reshape(-1, 3, 3); tmn = Tr.min(1); tmx = Tr.max(1)
    inside = np.all((tmx >= lo - 1e-6) & (tmn <= hi + 1e-6), axis=1).mean()       # triangle AABB overlaps the crop box (members spanning the box have no vertex inside)
    rows['TP' if e in G else 'FP'].append(round(float(inside), 2))
for k, l in rows.items(): print(k, len(l), 'frac triangles overlapping the crop box: min %.2f mean %.2f' % (min(l), sum(l) / len(l)), sorted(l)[:12])
