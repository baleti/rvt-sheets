"""cutfill_probe.py FILE VIEWID: per category of the view's elements: the cut fill our rules resolve (material, cut pattern) + prims drawn with fill"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
vd = ViewDrawer(dec, doc); dr = vd.draw(vid)
mats = vd.materials()
print('materials with a cut pattern:', [(m, (v.get('name'), v['cut_pattern'])) for m, v in mats.items() if (v.get('cut_pattern') or {}).get('id') is not None][:15])
c = collections.Counter()
for p in dr['prims']:
    if p.get('layer') in ('cut', 'cut_fill'):
        info = vd.vis.info.info.get(p.get('elem')) or {}
        c[(info.get('cls'), (doc['categories'].get(info.get('cat')) or {}).get('name'), p['t'], bool(p.get('fill')))] += 1
for k, n in c.most_common(25): print(n, k)
print('level detail', dr.get('detail_level'), 'stats', {k: v for k, v in vd.stats.items() if 'cut' in k})
