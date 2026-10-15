"""dump records: dump.py FILE CLASS [n] [maxlen]  or  dump.py FILE id:<eid>"""
import sys, os, json
sys.path.insert(0, os.path.expanduser('~/rvt-research'))
import rvt_xcache
x = rvt_xcache.get_x(sys.argv[1]); recs = x['recs']
n = int(sys.argv[3]) if len(sys.argv) > 3 else 1; ml = int(sys.argv[4]) if len(sys.argv) > 4 else 300
def short(v, d=0):
    s = repr(v) if not isinstance(v, (dict, list)) else json.dumps(v, default=repr)
    return s if len(s) <= ml else s[:ml] + '...(%d)' % len(s)
sel = []
if sys.argv[2].startswith('id:'):
    want = int(sys.argv[2][3:]); sel = [r for k, r in recs.items() if r['id'] == want]
else:
    sel = [r for r in recs.values() if r['class'] == sys.argv[2]][:n]
for r in sel:
    print('=== id', r['id'], r['class'], 'complete', r['complete'], r.get('error'))
    for k, v in r['fields'].items(): print('  ', k, '=', short(v))
