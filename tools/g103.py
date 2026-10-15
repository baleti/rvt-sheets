"""g103.py FILE id [depth] : tree of the saved-graphics (channel 103) record of an element: node classes + key fields"""
import sys, os, json, collections
sys.path.insert(0, os.path.expanduser('~/rvt-research'))
import rvt_elemmesh as EM
doc = EM.Doc(sys.argv[1]); eid = int(sys.argv[2]); maxd = int(sys.argv[3]) if len(sys.argv) > 3 else 6
r = doc.rec(eid)
if r is None: print('no g103 record'); sys.exit()
print(r['class'], 'complete', r['complete'])
cnt = collections.Counter()
def walk(n, d, key=''):
    if isinstance(n, dict) and 'obj' in n and 'ptr' in n:
        o = n['obj']; cnt[n['ptr']] += 1
        if d <= maxd:
            small = {k: v for k, v in (o.items() if isinstance(o, dict) else []) if not isinstance(v, (dict, list)) or (isinstance(v, list) and len(json.dumps(v, default=repr)) < 120)}
            print('  ' * d + key, n['ptr'], json.dumps(small, default=repr)[:260])
        if isinstance(o, dict):
            for k, v in o.items(): walk(v, d + 1, k)
        return
    if isinstance(n, dict):
        for k, v in n.items(): walk(v, d + 1, k)
    elif isinstance(n, list):
        for v in n: walk(v, d, key + '[]')
walk(r['fields'], 0)
import rvt_scan
c = rvt_scan.load(sys.argv[1])[1]
print({c[t - 12]['name']: k for t, k in cnt.items()})
