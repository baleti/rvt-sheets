"""width_audit.py FILE VIEWID REVIT.pdf : drawn ink length (dash gaps removed) per stroke width of our view vs the stroke-width totals of Revit's own PDF of the same view (page scales must match: only views exported at the view scale compare)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pymupdf
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
vd = ViewDrawer(dec, doc); dr = vd.draw(vid); sc = doc['views'][vid].get('scale') or 96
ours = collections.Counter(); k = 25.4 / 72
for p in dr['prims']:
    st = p.get('style') or {}; w = round((st.get('w') or 0), 2)
    if p.get('t') == 'line' and p.get('pts') is not None and len(p['pts']) > 1: pts = np.asarray(p['pts'], float); L = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    elif p.get('t') in ('segs', 'cut') and p.get('segs'): L = sum(float(np.linalg.norm(np.asarray(b, float) - np.asarray(a, float))) for a, b in p['segs'])
    else: continue
    L *= 304.8 / sc; d = st.get('dash'); L *= (sum(d[0::2]) / sum(d)) if d else 1.0
    ours[w] += L
page = pymupdf.open(sys.argv[3])[0]; rev = collections.Counter()
for d in page.get_drawings():
    w = d.get('width')
    if d.get('type') in ('s', 'fs') and w is not None: rev[round(w * k, 2)] += sum(((it[2].x - it[1].x) ** 2 + (it[2].y - it[1].y) ** 2) ** .5 for it in d['items'] if it[0] == 'l') * k
print('page mm', round(page.rect.width * k), round(page.rect.height * k), 'scale', sc)
for w in sorted(set(ours) | set(rev)):
    if ours.get(w, 0) > 30 or rev.get(w, 0) > 30: print('  w %.2f  ours %7.0f  revit %7.0f' % (w, ours.get(w, 0), rev.get(w, 0)))
