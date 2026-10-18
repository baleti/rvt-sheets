"""vg_filter_graphics.py SCENE.rte VIEWID... : resolved projection style (rgb, pen) of each element with filter hits in the views (compare with the scene's PNG/DXF: filters scene A = all walls red, B = mark-B walls green, others red)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.vg.resolve import resolve_view
dec = Decoder(sys.argv[1]); doc = dec.doc(); P = None
try: P = dec.f.params()
except Exception: P = {}
for vid in map(int, sys.argv[2:]):
    rep = resolve_view(dec, doc, vid)
    print(vid, rep['name'], 'filters', [(f['name'], f['visible'], f['overrides']) for f in rep['filters']])
    c = collections.Counter()
    for eid, row in rep['elements'].items():
        mark = ((P.get(eid) or {}).get('params') or {}).get('Mark')
        c[(row['cls'], mark, tuple(row['filters']), tuple(row['proj']['rgb']), row['proj']['pen'], row['transparency'])] += 1
    for k, n in sorted(c.items(), key=str):
        if k[2] or k[0] == 'SWall': print('  ', n, k)
