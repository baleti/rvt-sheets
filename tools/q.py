"""q.py FILE CLASS field1,field2,...  -> one line per record"""
import sys, os
sys.path.insert(0, os.path.expanduser('~/rvt-research'))
import rvt_xcache
x = rvt_xcache.get_x(sys.argv[1]); recs = x['recs']
fs = sys.argv[3].split(',')
def get(f, path):
    for p in path.split('.'):
        if isinstance(f, dict): f = f.get(p)
        elif isinstance(f, list) and p.isdigit() and int(p) < len(f): f = f[int(p)]
        else: return None
    return f
for r in sorted((r for r in recs.values() if r['class'] in sys.argv[2].split(',')), key=lambda r: r['id']):
    out = []
    for f in fs:
        v = get(r['fields'], f)
        s = repr(v); out.append(s[:int(os.environ.get('W', 60))])
    print(r['id'], r['class'][:14], ' | '.join(out))
