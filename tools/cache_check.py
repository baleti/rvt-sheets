"""cache_check.py FILE... : for each file the cache directory of the CURRENT drawing code + reader has every sheet and view SVG and no failed drawings
(what a demo needs for instant, cache-hit rendering). Light (no project load): runs anywhere. Exit 0 = all OK."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.cache import Cache
ok = True
for fn in sys.argv[1:]:
    c = Cache(fn); d = c.doc()
    if not d: print('FAIL', os.path.basename(fn), 'no doc.json for key', c.key); ok = False; continue
    miss = [k for k, ids in (('sheet', [s['id'] for s in d['sheets']]), ('view', [v['id'] for v in d['views']])) for i in ids if not c.has('%s_%d.svg' % (k, i))]
    try: failed = json.loads(c.read('failed.json'))
    except Exception: failed = []
    good = not miss and not failed
    ok &= good
    print('OK  ' if good else 'FAIL', os.path.basename(fn), 'key', c.key, '%d sheets %d views' % (len(d['sheets']), len(d['views'])), 'missing', len(miss), 'failed', len(failed))
print('CACHE CHECK OK' if ok else 'CACHE CHECK FAILED'); sys.exit(0 if ok else 1)
