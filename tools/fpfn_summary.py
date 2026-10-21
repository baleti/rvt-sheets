"""fpfn_summary.py FILE.rvt [ORACLE.views] : element-list FP / FN totals over all views by (class) and FN by (class, exclusion reason)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(sys.argv[2] if len(sys.argv) > 2 else oracle.find(fn))
dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
cls = lambda i: (dec.f.rec(i) or {}).get('class', '?')
fp = collections.Counter(); fnn = collections.Counter(); ex = collections.defaultdict(list)
for vid, ids in sorted(o['viewelems'].items()):
    v = doc['views'].get(vid)
    if not v or v.get('kind') in ('schedule', 'sheet'): continue
    pred, why = vis.elements(vid, explain=True); P = set(pred); G = set(ids)
    for i in P - G: fp[cls(i)] += 1; ex[('FP', cls(i))].append((vid, i))
    for i in G - P: k = (cls(i), why.get(i, 'not_candidate')); fnn[k] += 1; ex[('FN',) + k].append((vid, i))
print('FP by class', fp.most_common(15)); print('FN by class/reason', fnn.most_common(15))
for k, l in ex.items(): print(k, len(l), l[:4])
