"""fp_detail.py FILE.rvt CLASS [ORACLE.views] : false positives of one class per view with category name, type name guess, bbox z and phase info"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn, klass = sys.argv[1], sys.argv[2]; o = oracle.load(sys.argv[3] if len(sys.argv) > 3 else oracle.find(fn))
dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
for vid, ids in sorted(o['viewelems'].items()):
    v = doc['views'].get(vid)
    if not v or v.get('kind') in ('schedule', 'sheet'): continue
    pred = set(vis.elements(vid)); G = set(ids)
    for i in sorted(pred - G):
        e = vis.info.info[i]
        if e['cls'] != klass: continue
        bb = vis.info.bbox(i)
        print(vid, v['name'][:20], i, 'cat', e['cat'], (doc['categories'].get(e['cat']) or {}).get('name'), 'dopt', e['dopt'], 'ph', e['created'], e['demolished'], 'bb', None if bb is None else bb.round(1).tolist())
