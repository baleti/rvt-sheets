"""prim_lengths.py FILE VIEWID : drawn ink length (dash gaps removed) (paper mm) per (pen width, layer, element class) for one view, to compare with the stroke-width totals of Revit's PDF export of the same view"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
vd = ViewDrawer(dec, doc); dr = vd.draw(vid); sc = doc['views'][vid].get('scale') or 96
tot = collections.Counter(); byw = collections.Counter(); byel = collections.Counter(); bycat = collections.Counter()
def seglen(segs): return sum(float(np.linalg.norm(np.asarray(b, float) - np.asarray(a, float))) for a, b in segs) * 304.8 / sc
for p in dr['prims']:
    t = p.get('t'); st = p.get('style') or {}; w = round(st.get('w') or 0, 3)
    if t == 'line' and p.get('pts') is not None and len(p['pts']) > 1:
        pts = np.asarray(p['pts'], float); L = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()) * 304.8 / sc
    elif t in ('segs', 'cut') and p.get('segs'): L = seglen(p['segs'])
    else: continue
    dsh = st.get('dash')
    if dsh: L *= sum(dsh[0::2]) / max(sum(dsh), 1e-9)            # ink length of a dashed line (Revit's PDF carries the dashes as separate strokes)
    cls = vd.vis.info.info.get(p.get('elem'), {}).get('cls')
    tot[(w, p.get('layer'), cls)] += L; byw[w] += L
    if cls == 'FamilyInstance' and p.get('layer') == 'symbolic':
        byel[(p.get('elem'), w)] += L; bycat[(vd.vis.info.info.get(p.get('elem'), {}).get('cat'), w)] += L
print('by width', {k: round(v) for k, v in sorted(byw.items())})
for k, v in tot.most_common(22): print(round(v), k)
print('symbolic FamilyInstance by category (cat, width): ink mm', {k: round(v) for k, v in bycat.most_common(10)})
els = collections.Counter(); [els.update({e: v}) for (e, w), v in byel.items()]
print('top symbolic elements', [(e, round(v)) for e, v in els.most_common(8)], 'n elements', len(els))
if os.environ.get('PL_FAM'):
    import rvt_elemmesh
    for e, v in els.most_common(3):
        r = vd.f.rec(e); print('ELEM', e, r.get('class'), {k: str(x)[:60] for k, x in r['fields'].items() if 'ymbol' in k or 'amily' in k.lower()})
