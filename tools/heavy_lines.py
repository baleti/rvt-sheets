"""heavy_lines.py FILE VIEWID [MINW=0.4] : drawn line prims whose style weight (mm) is >= MINW, grouped by element / part / layer with total length (paper mm at the view scale)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2]); minw = float(sys.argv[3]) if len(sys.argv) > 3 else 0.4
dr = ViewDrawer(dec, doc).draw(vid); sc = doc['views'][vid].get('scale') or 100
c = collections.Counter(); n = collections.Counter()
for p in dr['prims']:
    if p.get("t") not in ("line", "poly", "region", "fill", "cut", "segs"): continue
    if os.environ.get('HL_KEYS') and p.get('t') == 'cut' and (p.get('style') or {}).get('w', 0) >= 0.4:
        sg = p['segs']; bb = np.array([q for s_ in sg for q in s_], float); print('CUT', p.get('elem'), 'nsegs', len(sg), 'bbox', bb.min(0).round(1).tolist(), bb.max(0).round(1).tolist(), 'len_ft', round(sum(float(np.linalg.norm(np.array(s_[-1]) - np.array(s_[0]))) for s_ in sg), 1))
    st = p.get('style') or {}; w = st.get('w') or st.get('weight') or 0
    if os.environ.get('HL_DBG') and not c: print(st); c['_'] += 0
    if w < minw: continue
    if p.get('segs') is not None and p.get('t') == 'segs': L = sum(float(np.linalg.norm(np.asarray(b, float) - np.asarray(a, float))) for a, b in p['segs']) * 304.8 / sc
    else:
        pts = np.asarray(p.get('pts') if p.get('pts') is not None else (p.get('outer') or [[0, 0]]), float); L = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()) * 304.8 / sc
    k = (p.get('t'), p.get('elem'), p.get('part'), p.get('layer'), round(w, 3)); c[k] += L; n[k] += 1
for k, v in c.most_common(25): print(round(v), n[k], k)
