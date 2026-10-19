"""prim_probe.py FILE VIEWID: drawn prims per (class, category, layer, type) and all draw stats"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
vd = ViewDrawer(dec, doc); dr = vd.draw(vid)
c = collections.Counter()
for p in dr['prims']:
    info = vd.vis.info.info.get(p.get('elem')) or {}
    c[(info.get('cls'), (doc['categories'].get(info.get('cat')) or {}).get('name'), p.get('layer'), p['t'])] += 1
for k, n in c.most_common(40): print(n, k)
print(dict(vd.stats))
v = doc['views'][vid]
print('display', {k: (v.get('display') or {}).get(k) for k in ('m_model',)}, 'detail', v.get('detail_level'), 'kind', v.get('kind'))
