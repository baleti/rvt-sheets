"""view_svg.py FILE VIEWID OUT.svg -> draw one view"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.viewsvg import view_svg
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
vd = ViewDrawer(dec, doc); t = time.time(); dr = vd.draw(vid)
v = doc['views'][vid]
from rvtsheets.compose import crop_rect_uv
open(sys.argv[3], 'w').write(view_svg(dr, v.get('scale') or 100, crop=crop_rect_uv(v), hang=os.environ.get('RVTSHEETS_HANG', '1') != '0'))
print(v['name'], v['kind'], 'scale', v.get('scale'), 'prims', len(dr['prims']), dr['stats'], dr.get('conds_unknown'), '%.1fs' % (time.time() - t))
