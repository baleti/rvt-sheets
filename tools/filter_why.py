"""filter_why.py FILE VIEWID : view filters that hide (visibility off) elements Revit lists, with the rule tree and a sample element's parameter value"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.filters import FilterEval
from rvtsheets import oracle
fn = sys.argv[1]; vid = int(sys.argv[2]); o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc); I = vis.info.info
fe = FilterEval(dec, doc); v = doc['views'][vid]; G = set(o['viewelems'][vid])
hits = collections.defaultdict(list)
for eid in G:
    if eid not in I: continue
    e = I[eid]
    for vf in v['filters']:
        f = doc['filters'].get(vf['filter'])
        if f and not vf['visible'] and vf.get('enabled') is not False and fe.matches(f, eid, e['cat'], (doc['categories'].get(e['cat']) or {}).get('parent', -1)): hits[vf['filter']].append(eid)
for fid, L in hits.items():
    f = doc['filters'][fid]; print(fid, f['name'], 'hides Revit-listed', len(L), 'cats', f['categories'][:6]); print('   rules', str(f['rules'])[:500])
    e = L[0]; print('   sample', e, I[e]['cls'], {k: x for k, x in ((fe.params().get(e) or {}).get('params') or {}).items() if k in ('Type Name', 'Family Name', 'Family and Type')})
for fid, L in hits.items():
    c = collections.Counter()
    for e in L:
        pe = (fe.params().get(e) or {}).get('params') or {}
        tid = pe.get('Family and Type'); tp = ((fe.params().get(tid) or {}).get('params') or {}) if isinstance(tid, int) else {}
        c[(tp.get('Family Name'), tp.get('Type Name'))] += 1
    print(fid, c.most_common(8))
