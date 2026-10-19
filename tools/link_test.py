"""link_test.py FILE VIEWID OUT.svg : draw a plan view with linked-model content (RVT_LINKS=1) and report the link stats"""
import sys, os
os.environ['RVT_LINKS'] = '1'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.viewsvg import view_svg
from rvtsheets.compose import crop_rect_uv
dec = Decoder(sys.argv[1]); doc = dec.doc(); dr = ViewDrawer(dec, doc); vid = int(sys.argv[2]); v = doc['views'][vid]
d = dr.draw(vid)
print({k: n for k, n in dr.stats.items() if 'link' in k}, getattr(dr, '_link_err', None), 'prims', len(d['prims']), 'link prims', sum(1 for p in d['prims'] if 'link' in p))
open(sys.argv[3], 'w').write(view_svg(d, v.get('scale') or 100, crop=crop_rect_uv(v)))
