"""view_svgs.py FILE GTDIR OUTDIR [kind,...] : view SVG (as view_svg.py) of every view of the given kinds (default 3d) that has a Revit PNG in GTDIR (host job); compare on host3 with tools/view_png_cmp.py"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.viewsvg import view_svg
from rvtsheets.compose import crop_rect_uv
fn, gt, out = sys.argv[1:4]; kinds = (sys.argv[4] if len(sys.argv) > 4 else '3d').split(',')
os.makedirs(out, exist_ok=True)
dec = Decoder(fn); doc = dec.doc(); vd = ViewDrawer(dec, doc)
for png in sorted(glob.glob(os.path.join(gt, '*.png'))):
    b = os.path.basename(png)[:-4]
    if not b.isdigit(): continue
    vid = int(b); v = doc['views'].get(vid)
    if not v or v['kind'] not in kinds: continue
    try:
        dr = vd.draw(vid)
        open(os.path.join(out, '%d.svg' % vid), 'w').write(view_svg(dr, v.get('scale') or 100, crop=crop_rect_uv(v), hang=True))
    except Exception as e: open(os.path.join(out, '%d.err' % vid), 'w').write(str(e))
open(os.path.join(out, 'DONE'), 'w').write('1')
