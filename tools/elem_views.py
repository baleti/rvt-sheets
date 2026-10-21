"""elem_views.py FILE.rvt EID [ORACLE.views] : bbox of the element and, per view, Revit-lists (GT) / we-list (pred) with view kind / name"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; eid = int(sys.argv[2]); o = oracle.load(sys.argv[3] if len(sys.argv) > 3 else oracle.find(fn))
dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
print('info', {k: x for k, x in vis.info.info[eid].items()}, 'bbox', None if vis.info.bbox(eid) is None else vis.info.bbox(eid).round(2).tolist())
for vid, ids in sorted(o['viewelems'].items()):
    v = doc['views'].get(vid)
    if not v or v.get('kind') in ('schedule', 'sheet'): continue
    pred, why = vis.elements(vid, explain=True)
    g = eid in ids; p = eid in pred
    print(vid, v['kind'], v['name'][:30], 'GT' if g else '--', 'PRED' if p else '----', '' if g == p else 'DIFF', why.get(eid, ''))
