"""rosetta_lists.py BASE.rte VAR.rte -> per view: elements Revit adds/removes between base and var (VIEWELEMS) vs the change our visibility model predicts.
Exact agreement = the V/G mechanism changed by the variant (category, filter, hidden element, phase filter, template...) is modelled."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
res = []
for fn in sys.argv[1:3]:
    o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
    res.append((o, doc, vis))
(oa, da, va), (ob_, db, vb) = res
cls = lambda i: (va.dec.f.rec(i) or vb.dec.f.rec(i) or {}).get('class', '?')
for vid in sorted(set(oa['viewelems']) & set(ob_['viewelems'])):
    v = db['views'].get(vid)
    if not v or v['kind'] in ('schedule', 'sheet'): continue
    ra, rb = set(oa['viewelems'][vid]), set(ob_['viewelems'][vid]); pa, pb = set(va.elements(vid)), set(vb.elements(vid))
    rem, add, prem, padd = ra - rb, rb - ra, pa - pb, pb - pa
    if rem or add or prem or padd:
        print(vid, v['kind'], v['name'], 'revit -%d +%d | ours -%d +%d | removed agree %d added agree %d' % (len(rem), len(add), len(prem), len(padd), len(rem & prem), len(add & padd)))
        import collections
        print('    revit removed', collections.Counter(cls(i) for i in rem).most_common(5), 'added', collections.Counter(cls(i) for i in add).most_common(5))
