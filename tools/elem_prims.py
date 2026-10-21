"""elem_prims.py FILE VIEWID EID... : the drawn prims of the given elements (type, layer, style width / pen / dash, point count, rounded first segment), to see duplicated or overlapping strokes"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2]); eids = set(map(int, sys.argv[3:]))
vd = ViewDrawer(dec, doc); dr = vd.draw(vid)
v = doc['views'][vid]; print('view', v.get('name'), 'detail_level', v.get('detail_level'), 'scale', v.get('scale'))
for p in dr['prims']:
    if p.get('elem') not in eids: continue
    st = p.get('style') or {}
    pts = p.get('pts') if p.get('pts') is not None else (p['segs'][0] if p.get('segs') else None)
    print(p.get('elem'), p.get('t'), p.get('layer'), p.get('part'), 'w', st.get('w'), 'pen', st.get('pen'), 'dash', st.get('dash') is not None, 'n', len(p.get('pts') or p.get('segs') or []), np.round(np.asarray(pts, float), 2).tolist()[:2] if pts is not None else None)
