"""filter_dump.py FILE FILTERID ELEMID... : full rule tree of a filter and the values of the rule parameters on the elements"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.filters import FilterEval
dec = Decoder(sys.argv[1]); doc = dec.doc(); f = doc['filters'][int(sys.argv[2])]; fe = FilterEval(dec, doc)
print(json.dumps(f.get('rules'), default=str, indent=1)[:9000])
def leaves(r):
    if r is None: return
    if 'children' in r:
        for c in r['children']: yield from leaves(c)
    elif r.get('rule') == 'FilterInverseRule': yield r['inner']
    else: yield r
for e in map(int, sys.argv[3:]):
    print('elem', e, [(l.get('param_name'), l.get('param'), fe.value(e, l)) for l in leaves(f.get('rules'))], 'params', list(((fe.params().get(e) or {}).get('params') or {}).items())[:40])
