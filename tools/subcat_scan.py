"""subcat_scan.py FILE : views whose category overrides set a PARENT category (that has sub-categories) with / without an own override on the sub-categories"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.reader import INVALID
dec = Decoder(sys.argv[1]); doc = dec.doc(); cats = doc['categories']
kids = {}
for cid, c in cats.items():
    p = c.get('parent', INVALID)
    if p not in (INVALID, None): kids.setdefault(p, []).append(cid)
n = 0
for vid, v in doc['views'].items():
    co = v.get('category_overrides') or {}
    for p, ks in kids.items():
        if p in co and co[p]:
            own = [k for k in ks if co.get(k)]
            print(vid, v['name'][:30], 'parent', p, cats[p].get('name'), 'subs', len(ks), 'with own override', len(own), sorted(co[p])[:5] if isinstance(co[p], dict) else ''); n += 1
print('rows', n)
