"""pdf_weights_all.py FILE [VIEWIDS] : stroke length per line width (mm) of Revit's per-view PDF vs our view SVG; prints the classes where the lengths differ most.
The PDF may be scaled (fit to page): the ratio of the dominant class is printed and the others are compared after dividing by it."""
import sys, os, glob, math, re, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.expanduser('~/src/rvt-qa'))
import pymupdf
from qa import pdfvec
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.viewsvg import view_svg
from rvtsheets.compose import crop_rect_uv
fn = sys.argv[1]; base = os.path.splitext(os.path.basename(fn))[0]
gt = sorted(d for d in glob.glob(os.path.expanduser('~/rvt-research/gt_views/*')) if d.endswith(base) and os.path.isdir(d))[-1]
ids = [int(x) for x in sys.argv[2:]] or sorted(int(os.path.basename(p)[:-4]) for p in glob.glob(gt + '/*.pdf') if os.path.basename(p)[:-4].isdigit())
dec = Decoder(fn); doc = dec.doc(); d = ViewDrawer(dec, doc)
for vid in ids:
    v = doc['views'].get(vid)
    if not v or v.get('kind') in ('sheet', 'schedule', 'legend', '3d') or vid in doc.get('sheets', {}): continue
    try:
        svg = view_svg(d.draw(vid), v.get('scale') or 100, margin_mm=0, crop=crop_rect_uv(v))
        P = pdfvec.pdf_weights(os.path.join(gt, '%d.pdf' % vid)); O = pdfvec.svg_weights(svg)
        tp = sum(P.values()); to = sum(O.values()); k = tp / to if to else 0
        rows = []
        for w in sorted(set(P) | set(O)):
            a = P.get(w, 0); b = O.get(w, 0)
            if max(a, b) > 0.03 * max(tp, to): rows.append((w, a, b))
        print('%d %s revit %.0f mm ours %.0f mm  scale-ratio %.3f' % (vid, v['name'][:26], tp, to, k))
        for w, a, b in rows: print('    w %.2f  revit %8.0f  ours %8.0f' % (w, a, b))
    except Exception as ex:
        print(vid, 'ERR', repr(ex)[:100])
