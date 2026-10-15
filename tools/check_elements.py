"""check_elements.py FILE.rvt [ORACLE.views] [viewid...] -> per-view precision/recall of the predicted visible element set vs Revit's
FilteredElementCollector(doc, viewId); with view ids: class breakdown of false positives / negatives and exclusion reasons."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle

fn = sys.argv[1]
args = sys.argv[2:]
ofn = args.pop(0) if args and args[0].endswith('.views') else oracle.find(fn)
only = [int(a) for a in args]
o = oracle.load(ofn); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
tot = collections.Counter(); bykind = collections.defaultdict(collections.Counter)
for vid, ids in sorted(o['viewelems'].items()):
    if only and vid not in only: continue
    v = doc['views'].get(vid)
    if not v or v.get('kind') in ('schedule', 'sheet'): continue
    pred, why = vis.elements(vid, explain=True)
    P = set(pred); G = set(ids)
    tp = len(P & G); fp = len(P - G); fn_ = len(G - P)
    tot.update(tp=tp, fp=fp, fn=fn_); bykind[v['kind']].update(tp=tp, fp=fp, fn=fn_)
    print('%8d %-10s %-40s gt %5d pred %5d  P %.3f R %.3f' % (vid, v['kind'], v['name'][:40], len(G), len(P), tp / max(len(P), 1), tp / max(len(G), 1)))
    if only:
        cls = lambda i: (dec.f.rec(i) or {}).get('class', '?')
        print('   FP', collections.Counter(cls(i) for i in P - G).most_common(12))
        print('   FN', collections.Counter((cls(i), why.get(i, 'not_candidate')) for i in G - P).most_common(12))
for k, c in list(bykind.items()) + [('ALL', tot)]:
    print('%-10s precision %.4f recall %.4f  (tp %d fp %d fn %d)' % (k, c['tp'] / max(c['tp'] + c['fp'], 1), c['tp'] / max(c['tp'] + c['fn'], 1), c['tp'], c['fp'], c['fn']))
