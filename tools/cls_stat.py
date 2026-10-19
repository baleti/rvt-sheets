"""cls_stat.py FILE CLASS : per view kind TP / FP / FN counts of one element class vs Revit's lists, plus plan views where it is TP (with cut / bottom)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn, cls = sys.argv[1], sys.argv[2]
o = oracle.load(oracle.find(fn)); d = Decoder(fn); doc = d.doc(); vis = Visibility(d, doc); c = collections.Counter()
for vid, ids in o['viewelems'].items():
    v = doc['views'].get(vid)
    if not v or v.get('kind') in ('schedule', 'sheet'): continue
    P = set(vis.elements(vid)); G = set(ids); r = (vis.effective(v).get('range') or {}) if v['kind'] == 'plan' else {}
    for e in P | G:
        if vis.info.info.get(e, {}).get('cls') != cls: continue
        t = 'TP' if e in P and e in G else 'FP' if e in P else 'FN'; c[(v['kind'], t)] += 1
        if v['kind'] == 'plan' and t != 'FN': c[(v['name'][:16], t, 'cut', r.get('cut'), 'bot', r.get('bottom'))] += 1
for k, n in sorted(c.items(), key=str): print(k, n)
