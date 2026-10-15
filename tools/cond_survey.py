"""cond_survey.py FILE [maxrec] -> counts of saved-graphics condition kinds (class, comp, param, value/dir)"""
import sys, os, collections, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.reader import File
f = File(sys.argv[1]); mx = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
cnt = collections.Counter(); ex = {}
n = 0
for eid, info in f.g.res.items():
    if not (info.get('bodies') or {}).get('GFilter') and not (info.get('bodies') or {}).get('GGroup'): continue
    r = f.graphics(eid); n += 1
    if n > mx: break
    def walk(x, depth=0):
        if isinstance(x, dict):
            if 'ptr' in x and 'obj' in x and isinstance(x['obj'], dict) and 'm_oConditions' in x['obj']:
                for c in x['obj']['m_oConditions']:
                    cls = f.tagname(c.get('ptr')); o = c.get('obj') or {}
                    key = (cls,) + tuple((k, tuple(v) if isinstance(v, list) else v) for k, v in sorted(o.items()) if k != 'm_dir') + ((('dir', tuple(round(a, 3) for a in o['m_dir'])),) if 'm_dir' in o else ())
                    cnt[key] += 1; ex.setdefault(key, (eid, f.rec(eid)['class'] if f.rec(eid) else '?'))
            for v in x.values(): walk(v, depth + 1)
        elif isinstance(x, list):
            for v in x: walk(v, depth + 1)
    walk(r['fields'])
for k, c in cnt.most_common(60): print(c, k, ex[k])
