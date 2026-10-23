"""framing_prims.py FILE VIEWID [N]: structural framing (-2001320) elements of a view: type name, header bbox size, prim count / flags drawn (first N)"""
import sys, os, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); vid = int(sys.argv[2]); n = int(sys.argv[3]) if len(sys.argv) > 3 else 12
dr = vd.draw(vid); I = vd.vis.info.info; by = collections.defaultdict(list)
for p in dr['prims']: by[p.get('elem')].append(p)
cnt = collections.Counter(); shown = 0
for e in vd.vis.elements(vid):
    if I[e]['cat'] != -2001320: continue
    r = d.f.rec(e); fl = r['fields']; ps = by.get(e, [])
    bb = vd.vis.info.bbox(e); sz = None if bb is None else np.round(bb[1] - bb[0], 2).tolist()
    ii = fl.get('m_pInstanceInfo') or {}
    sid = d.f.eid((ii.get('obj', ii) or {}).get('m_symbolId')) if ii else None
    st = d.f.rec(sid) if sid not in (None, -1) else None
    nm = str(((st or {}).get('fields') or {}).get('m_symbolInfo', ''))[-60:]
    key = (I[e]['cls'], sid); cnt[key] += 1
    if shown < n: shown += 1; print(e, I[e]['cls'], 'sym', sid, nm, 'bbox', sz, 'prims', len(ps), collections.Counter((p['t'], p.get('layer')) for p in ps).most_common(3))
print(cnt.most_common(8))
