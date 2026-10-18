"""vg_phase_graphics.py SCENE.rte VIEWID... : resolved style per (class, phase status) with the phase-override members (compare with the scene PNG)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.vg.resolve import resolve_view
dec = Decoder(sys.argv[1]); doc = dec.doc()
print('phase filters', [(p['name'], p['presentation']) for p in doc['phase_filters']])
print('phase_overrides', doc.get('phase_overrides'))
for vid in map(int, sys.argv[2:]):
    rep = resolve_view(dec, doc, vid); v = doc['views'][vid]
    print(vid, rep['name'], 'phase', v['phase'], 'pf', v['phase_filter'])
    c = collections.Counter()
    for eid, row in rep['elements'].items():
        c[(row['cls'], row['phase'], tuple(sorted((k, str(x)) for k, x in row['overrides'].items())), tuple(row['proj']['rgb']), row['proj']['pen'])] += 1
    for k, n in sorted(c.items(), key=str):
        if k[0] in ('SWall', 'FamilyInstance', 'Floor'): print('  ', n, k)
