"""pen_elems.py FILE VIEWID WIDTH : elements that draw lines of the given pen width (mm), ink length, family / type names, to find what Revit's export does not draw"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.reader import ob
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2]); W = float(sys.argv[3])
vd = ViewDrawer(dec, doc); dr = vd.draw(vid); sc = doc['views'][vid].get('scale') or 96
ink = collections.Counter(); n = collections.Counter()
for p in dr['prims']:
    st = p.get('style') or {}
    if abs((st.get('w') or 0) - W) > 0.004 or p.get('t') != 'line' or p.get('pts') is None: continue
    pts = np.asarray(p['pts'], float); L = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()) * 304.8 / sc
    d = st.get('dash'); L *= (sum(d[0::2]) / sum(d)) if d else 1.0
    ink[p.get('elem')] += L; n[p.get('elem')] += 1
f = vd.f; names = collections.Counter(); per_type = collections.Counter()
for e, L in ink.most_common():
    r = f.rec(e); fl = (r or {}).get('fields', {})
    sid = f.eid(fl.get('m_symbolId')) if fl.get('m_symbolId') is not None else None
    sr = f.rec(sid) if sid is not None else None
    nm = ((ob((sr or {}).get('fields', {}).get('m_symbolInfo')) or {}).get('m_name'))
    names[nm] += 1; per_type[nm] += L
print('elements', len(ink), 'total ink', round(sum(ink.values())))
for nm, L in per_type.most_common(12): print(round(L), names[nm], nm)
print('top elements', [(e, round(L), n[e]) for e, L in ink.most_common(5)])
