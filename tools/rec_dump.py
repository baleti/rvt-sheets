"""rec_dump.py FILE CLASS|#ID [N] [MAXDEPTH]: the first N records of a class as an indented field tree (values clipped)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); n = int(sys.argv[3]) if len(sys.argv) > 3 else 1; md = int(sys.argv[4]) if len(sys.argv) > 4 else 6
def show(x, ind=0, depth=0):
    if depth > md: print(' ' * ind + '...'); return
    if isinstance(x, dict):
        for k, v in x.items():
            if isinstance(v, (dict, list)) and len(str(v)) > 100: print(' ' * ind + str(k) + ':'); show(v, ind + 2, depth + 1)
            else: print(' ' * ind + str(k), str(v)[:150])
    elif isinstance(x, list):
        for i, v in enumerate(x[:5]):
            print(' ' * ind + '[%d]' % i); show(v, ind + 2, depth + 1)
        if len(x) > 5: print(' ' * ind + '... %d more' % (len(x) - 5))
recs = [d.f.rec(int(sys.argv[2][1:]))] if sys.argv[2].startswith('#') else d.f.recs(sys.argv[2])[:n]
for r in recs:
    print('== id', r['id']); show(r['fields'])
