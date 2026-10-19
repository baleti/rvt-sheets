"""fp_report.py FILE [CLASS...] : element-list disagreement report vs Revit's collector lists (run on host1).
Totals of FP / FN per (view kind, class); for the given classes (default: the 4 most frequent FP classes) per element: in how many views it is TP / FP, bbox z, owner, phase."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; want = sys.argv[2:]
o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
fp = collections.Counter(); fnc = collections.Counter(); per = collections.defaultdict(lambda: [0, 0, set()])
for vid, ids in o['viewelems'].items():
    v = doc['views'].get(vid)
    if not v or v.get('kind') in ('schedule', 'sheet'): continue
    pred, why = vis.elements(vid, explain=True); P = set(pred); G = set(ids)
    for e in P - G: fp[(v['kind'], vis.info.info[e]['cls'])] += 1; per[e][1] += 1; per[e][2].add(v['name'][:18])
    for e in P & G: per[e][0] += 1
    for e in G - P: fnc[(v['kind'], vis.info.info.get(e, {}).get('cls'), why.get(e))] += 1
print('FP'); [print(' ', k, n) for k, n in fp.most_common(25)]
print('FN'); [print(' ', k, n) for k, n in fnc.most_common(15)]
top = want or [c for c, _ in collections.Counter({k[1]: n for k, n in fp.items()}).most_common(4)]
for c in top:
    print('==', c)
    for e, (tp, f, names) in sorted(per.items()):
        i = vis.info.info[e]
        if i['cls'] != c or not f: continue
        bb = vis.info.bbox(e)
        print(' ', e, 'TPviews', tp, 'FPviews', f, 'z', None if bb is None else [round(float(x), 1) for x in bb[:, 2]], 'phase', i['created'], sorted(names)[:4])
