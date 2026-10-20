"""view_filters.py FILE VIEWID ELEMID... : the view's filter list (visible / enabled) and whether each filter matches the elements"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.filters import FilterEval
dec = Decoder(sys.argv[1]); doc = dec.doc(); v = doc['views'][int(sys.argv[2])]; fe = FilterEval(dec, doc)
from rvtsheets.visibility import Visibility
vis = Visibility(dec, doc)
for vf in v.get('filters') or []:
    f = doc['filters'].get(vf['filter']) or {}
    print(vf['filter'], f.get('name'), 'visible', vf.get('visible'), 'enabled', vf.get('enabled'), 'cats', (f.get('categories') or [])[:6], 'rules', str(f.get('rules'))[:200])
    for e in map(int, sys.argv[3:]):
        i = vis.info.info[e]; par = (doc['categories'].get(i['cat']) or {}).get('parent', -1)
        print('    elem', e, i['cat'], 'matches', fe.matches(f, e, i['cat'], par))
