"""filter_probe.py FILE VIEWID FILTERID...: print the filter rules and, per matching/near-miss framing element, the parameter the rule reads"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.filters import FilterEval
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
vis = Visibility(dec, doc); fe = FilterEval(dec, doc)
shown, why = vis.elements(vid, explain=True)
for fid in map(int, sys.argv[3:]):
    f = doc['filters'][fid]
    print('FILTER', fid, f.get('name'), 'cats', f.get('categories'), '\n rules', f.get('rules'))
    names = set()
    def walk(r):
        if r is None: return
        if 'children' in r: [walk(c) for c in r['children']]
        if 'inner' in r: walk(r['inner'])
        if r.get('param_name'): names.add(r['param_name'])
    walk(f.get('rules'))
    n = m = 0; vals = collections.Counter(); ex = []
    for eid in shown:
        e = vis.info.info[eid]
        if e['cat'] not in (f.get('categories') or []): continue
        n += 1
        ok = fe.matches(f, eid, e['cat'])
        m += ok
        pe = (fe.params().get(eid) or {}).get('params') or {}
        for nm in names: vals[(nm, repr(pe.get(nm)), ok)] += 1
        if not ok and len(ex) < 3: ex.append((eid, {k: v for k, v in pe.items() if 'ffset' in k or 'Level' in k}))
    print(' in-category shown', n, 'matching', m)
    for k, c in vals.most_common(15): print('  ', k, c)
    print(' non-matching examples', ex)
