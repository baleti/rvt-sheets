"""fn_reasons.py FILE.rvt [fp|fn] -> element-list errors against Revit's per-view lists aggregated over all views, by (class, reason)."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; mode = sys.argv[2] if len(sys.argv) > 2 else 'fn'
o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
cls = lambda i: (dec.f.rec(i) or {}).get('class', '?'); c = collections.Counter(); kinds = collections.defaultdict(set)
for vid, ids in sorted(o['viewelems'].items()):
    v = doc['views'].get(vid)
    if not v or v.get('kind') in ('schedule', 'sheet'): continue
    pred, why = vis.elements(vid, explain=True); P = set(pred); G = set(ids)
    for i in (G - P if mode == 'fn' else P - G):
        k = (v['kind'], cls(i), why.get(i, 'not_candidate') if mode == 'fn' else 'listed'); c[k] += 1; kinds[k].add(vid)
for k, n in c.most_common(25): print(n, k, 'views', len(kinds[k]))
