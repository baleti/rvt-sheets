"""above_cut_stat.py FILE : plan views (not ceiling plans): elements wholly above the cut plane (bbox bottom > cut) that we list: TP / FP per category vs Revit's lists"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); d = Decoder(fn); doc = d.doc(); vis = Visibility(d, doc); c = collections.Counter()
for vid, ids in o['viewelems'].items():
    v = doc['views'].get(vid)
    if not v or v['kind'] != 'plan': continue
    r = vis.effective(v).get('range') or {}
    if r.get('plan_view_type') == 2 or r.get('cut') is None: continue
    P = set(vis.elements(vid)); G = set(ids)
    for e in P | G:
        bb = vis.info.bbox(e)
        if bb is None or bb[0][2] <= r['cut'] + 1e-3: continue
        i = vis.info.info[e]; c[((doc['categories'].get(i['cat']) or {}).get('name'), i['cls'], 'TP' if e in P and e in G else 'FP' if e in P else 'FN')] += 1
for k, n in sorted(c.items(), key=str): print(k, n)
