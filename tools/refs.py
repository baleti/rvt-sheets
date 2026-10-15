"""refs.py FILE id[,id..] -> records whose fields mention the id (as EID or int), with field path"""
import sys, os
sys.path.insert(0, os.path.expanduser('~/rvt-research'))
import rvt_xcache
x = rvt_xcache.get_x(sys.argv[1]); recs = x['recs']
want = set(int(a) for a in sys.argv[2].split(','))
def walk(v, path, out):
    if isinstance(v, dict):
        for k, w in v.items(): walk(w, path + '.' + str(k), out)
    elif isinstance(v, (list, tuple)):
        for i, w in enumerate(v): walk(w, path + '[%d]' % i, out)
    else:
        try:
            if type(v).__name__ in ('EID', 'int') and int(v) in want: out.append((path, int(v)))
        except Exception: pass
for r in recs.values():
    out = []; walk(r['fields'], '', out)
    out = [o for o in out if not (o[0] == '.m_id')]
    if out: print(r['id'], r['class'], out[:6])
