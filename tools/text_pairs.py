"""text_pairs.py FILE.rvt VIEWID [GTDIR] : per matched text (Revit DXF vs ours) the offset in paper mm (ours - Revit, x right / y down as in the SVG),
grouped by owner element class + text type; lists missing / extra texts with owner class. Uses rvt-qa's vec module (no cv2). Run on host1 (h1run)."""
import sys, os, re, math, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.expanduser('~/src/rvt-qa'))
import numpy as np
from qa import vec
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.viewsvg import view_svg
from rvtsheets.compose import crop_rect_uv
fn, vid = sys.argv[1], int(sys.argv[2])
gt = sys.argv[3] if len(sys.argv) > 3 else None
if not gt:
    import glob
    base = os.path.splitext(os.path.basename(fn))[0]
    cands = [d for d in glob.glob(os.path.expanduser('~/rvt-research/gt_views/*')) if d.endswith(base) and os.path.isdir(d)]
    gt = sorted(cands)[-1]
dec = Decoder(fn); doc = dec.doc(); vd = ViewDrawer(dec, doc); v = doc['views'][vid]
svg = view_svg(vd.draw(vid), v.get('scale') or 100, margin_mm=0, crop=crop_rect_uv(v))
ours = vec.svg_texts(svg); ref, k = vec.dxf_texts(os.path.join(gt, '%d.dxf' % vid))
S = 304.8 / v['scale']
R = [dict(r, x=r['x'] * S, y=-r['y'] * S, h=r['h'] * S * 1.389) for r in ref]
sc, tx, ty, nv = vec.vote_registration(ours, R)
if sc is None: sc, tx, ty, nv = vec.vote_registration(ours, R, tol=8.0, cands=[1.0, 0.99, 1.01])
print("registration", sc, tx, ty, nv, "ours", len(ours), "ref", len(ref), [o["t"] for o in ours][:8], [r["t"] for r in ref][:8])
if sc is None: sys.exit(1)
m, mi, ex = vec.compare_texts(ours, R, sc, tx, ty); tx, ty = vec.compare_texts.last
print('view', vid, v['name'], 'revit', len(ref), 'ours', len(ours), 'votes', nv, 'matched', len(m), 'missing', len(mi), 'extra', len(ex))
def cls(e):
    try: return vd.f.rec(int(e))['class']
    except Exception: return '?'
G = collections.defaultdict(list)
for r, o, d in m:
    lx, ly = vec.left_edge_xy(o); dx = lx - (sc * r['x'] + tx); dy = ly - (sc * r['y'] + ty)
    G[(cls(o.get('e')), o.get('font'), round(o['h'], 1), r.get('layer'))].append((dx, dy, o['t'], o.get('e'), o.get('rot'), o.get('anchor'), r.get('rot'), r.get('anchor'), sorted(r.keys())))
if os.environ.get('TP_DETAIL'):
    for key, L in G.items():
        if key[3] == os.environ['TP_DETAIL']:
            for x in L[:40]: print('DETAIL', key[0], x[2], x[3], 'dx %+.1f dy %+.1f' % (x[0], x[1]), 'ours rot/anchor', x[4], x[5], 'rev rot/anchor', x[6], x[7], x[8])
    print('okeys', sorted(m[0][1].keys()))
for key, L in sorted(G.items(), key=lambda kv: -len(kv[1])):
    a = np.array([(x[0], x[1]) for x in L])
    print('%-22s %-14s h%-5s %-14s n=%3d  dx med %+5.1f [%+5.1f..%+5.1f]  dy med %+5.1f [%+5.1f..%+5.1f]' % (key[0], str(key[1])[:14], key[2], key[3], len(L), np.median(a[:, 0]), a[:, 0].min(), a[:, 0].max(), np.median(a[:, 1]), a[:, 1].min(), a[:, 1].max()), [(x[2][:14], x[3]) for x in L[:2]])
print('MISSING'); c = collections.Counter((re.sub(r'\d+', '#', x['t'])[:30], x['layer']) for x in mi)
for kk, n in c.most_common(25): print('  ', n, kk)
print('EXTRA'); c = collections.Counter((cls(x.get('e')), re.sub(r'\d+', '#', x['t'])[:30]) for x in ex)
for kk, n in c.most_common(25): print('  ', n, kk)
