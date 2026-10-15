"""timing.py FILE... : first render (warm's per-drawing timings.json) vs cached serving (fresh standalone server, every drawing over HTTP)
-> markdown table rows. Run after `rvt-sheets warm FILE`."""
import sys, os, json, time, subprocess, random, statistics, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.cache import Cache
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(url):
    t = time.time(); r = urllib.request.urlopen(url, timeout=600); b = r.read(); return time.time() - t, r.headers.get('X-Rvt-Cache'), len(b)


print('| file | sheets | views | first render: total / median / max (s) | server start to page ready (s) | cached: median / max (ms) | cache hits |')
print('|---|---|---|---|---|---|---|')
for f in sys.argv[1:]:
    f = os.path.abspath(f); c = Cache(f); d = c.doc()
    if not d: print('| %s | not warmed |' % os.path.basename(f)); continue
    tm = json.loads(c.read('timings.json')); first = list(tm.values())
    port = random.randint(20000, 40000); t0 = time.time()
    p = subprocess.Popen([os.path.join(REPO, 'rvt-sheets'), 'serve', f, '--port', str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = 'http://127.0.0.1:%d/sheets/api/local' % port
    try:
        for _ in range(600):
            try:
                if json.loads(urllib.request.urlopen(base + '/status').read())['state'] == 'ready': break
            except Exception: pass
            time.sleep(0.05)
        get(base + '/doc.json'); ready = time.time() - t0
        ts = []; hits = 0
        for k, xs in (('sheet', d['sheets']), ('view', d['views'])):
            for x in xs:
                dt, h, n = get('%s/%s/%d.svg' % (base, k, x['id'])); ts.append(dt); hits += h == 'hit'
    finally: p.terminate(); p.wait()
    print('| %s | %d | %d | %.0f / %.1f / %.1f | %.1f | %.1f / %.1f | %d/%d |' % (os.path.basename(f), len(d['sheets']), len(d['views']), sum(first),
          statistics.median(first), max(first), ready, 1000 * statistics.median(ts), 1000 * max(ts), hits, len(ts)))
