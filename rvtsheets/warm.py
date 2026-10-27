"""rvt-sheets warm FILE... : pre-render every sheet and drawable view of each file into the persistent cache (rvtsheets.cache).
  --workers N   parallel renderers (default: as many as fit in --mem, at most 4)
  --mem SIZE    memory cap for the whole job (default 3G; on host3 the job re-runs itself inside a systemd scope with that cap)
  --host1       run on host1 through h1run (for big files), then pull the cache back
  --port N      port printed in the demo command (READY.json)
  --refresh     redraw everything (e.g. after reader changes; the cache key does not include the reader version)
Each worker is its own process with its own decoder (the reader cache makes a re-open take seconds); a worker killed by the memory
cap only loses its current drawing: the remaining ones are retried with fewer workers. Prints one progress line per drawing and the
final line `warmed N sheets, M views` (exit 0 when every drawing is cached, 1 when some failed)."""
import os, sys, json, time, shutil, subprocess, argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
import multiprocessing as mp

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
H1RUN = os.path.expanduser('~/.local/share/offload/h1run')


def rss_mb():
    try: return int(open('/proc/self/statm').read().split()[1]) * 4096 // 2 ** 20
    except Exception: return 0


def parse_mem(s):
    s = s.strip().upper(); f = {'K': 2 ** -10, 'M': 1, 'G': 1024}.get(s[-1:], None)
    return int(float(s[:-1]) * f) if f else int(s) // 2 ** 20


# ---- worker process
_m = None


def _init(path, key):
    global _m
    sys.path.insert(0, REPO)
    from rvtsheets.drawings import Model
    from rvtsheets.cache import Cache
    _m = Model(path); _m.cache = Cache(path, key); _m.decoder()


def _draw(kind, eid):
    from rvtsheets.drawings import render
    name = '%s_%d.svg' % (kind, eid)
    if _m.cache.has(name): return kind, eid, 0.0, None, rss_mb()
    t = time.time()
    try:
        _m.cache.write(name, render(_m, kind, eid))
        _m.cache.thumb(kind, eid)
        return kind, eid, time.time() - t, None, rss_mb()
    except Exception as ex:
        return kind, eid, time.time() - t, '%s: %s' % (type(ex).__name__, str(ex)[:200]), rss_mb()


# ---- one file
def warm_file(path, workers=None, mem_mb=3072, port=8810, out=print, refresh=False):
    from rvtsheets.drawings import Model
    from rvtsheets.cache import mark_ready
    t0 = time.time()
    m = Model(path)
    if refresh:
        for n in os.listdir(m.dir):
            if n.endswith(('.svg', '.png')) or n == 'doc.json': os.remove(os.path.join(m.dir, n))
        m._summary = None
        m.cache.write('meta.json', json.dumps({'path': m.cache.path, 'parts': m.cache.parts, 'created': time.strftime('%Y-%m-%d %H:%M:%S')}))
    if m._summary is None:
        out('%s: decoding (first open of this file version)...' % os.path.basename(path))
        m.decoder(); m._summary = m._make_summary(); m.cache.write('doc.json', json.dumps(m._summary))
        m.cache.write('load_seconds', '%.1f' % (time.time() - t0))
    s = m._summary
    names = {('sheet', x['id']): '%s %s' % (x['number'], x['name']) for x in s['sheets']}
    names.update({('view', x['id']): '[%s] %s' % (x['kind'], x['name']) for x in s['views']})
    todo = [k for k in names if not m.cache.has('%s_%d.svg' % k)]
    timings = {}
    try: timings = json.loads(m.cache.read('timings.json'))
    except Exception: pass
    base_rss = rss_mb() if m._doc is not None else 0
    per = max(900, int(2.7 * base_rss)) if base_rss else max(900, int(m.size / 1e6 * 60))     # per-worker estimate (MB)
    w = workers or max(1, min(4, os.cpu_count() or 1, (mem_mb - base_rss) // per))
    m._dec = m._doc = m._drawer = None                                                          # free the parent's model before forking work
    n0 = len(names) - len(todo); done = n0; failed = {}
    out('%s: %d sheets, %d views, %d cached, %d to draw with %d worker%s (cap %d MB)' % (
        os.path.basename(path), len(s['sheets']), len(s['views']), n0, len(todo), w, 's' if w > 1 else '', mem_mb))
    # expensive first (sheets carry several views) so the slowest drawing does not start last
    todo.sort(key=lambda k: (-timings.get('%s_%d' % k, 30 if k[0] == 'sheet' else 5)))
    tries = {}
    while todo:
        ctx = mp.get_context('spawn')
        broken = False
        with ProcessPoolExecutor(max_workers=w, mp_context=ctx, initializer=_init, initargs=(path, m.key)) as ex:
            futs = {ex.submit(_draw, *k): k for k in todo}
            try:
                for f in as_completed(futs):
                    kind, eid, sec, err, rss = f.result()
                    k = (kind, eid); todo.remove(k); done += 1
                    if err: failed[k] = err
                    else: timings['%s_%d' % k] = round(sec, 2)
                    out('[%d/%d] %-5s %-48s %6.1fs %s' % (done, len(names), kind, names[k][:48], sec, ('FAILED ' + err) if err else '%d MB' % rss))
            except BrokenProcessPool:
                broken = True
        if broken:
            for k in todo: tries[k] = tries.get(k, 0) + 1
            if w > 1: w = max(1, w // 2); out('a worker hit the memory cap: retrying %d drawings with %d worker(s)' % (len(todo), w))
            else:
                k = todo[0]; failed[k] = 'killed (memory cap %d MB)' % mem_mb; todo.remove(k); done += 1          # give up on the culprit
                out('[%d/%d] %-5s %-48s FAILED (memory cap)' % (done, len(names), k[0], names[k][:48]))
    m.cache.write('timings.json', json.dumps(timings))
    m.cache.write('failed.json', json.dumps({'%s_%d' % k: v for k, v in failed.items()}))
    secs = time.time() - t0
    mark_ready(m.cache, s, secs, port, failed=len(failed))
    prune_old(m.cache)
    ns = sum(1 for k in names if k[0] == 'sheet' and k not in failed); nv = sum(1 for k in names if k[0] == 'view' and k not in failed)
    return ns, nv, failed, secs


def prune_old(cache, keep=2):
    """delete cache directories of older versions of the same file, keeping the `keep` newest others (the server falls back to the
    newest complete one when the running code has no cache: demo tree vs dev tree, reader updates)"""
    from rvtsheets.cache import ROOT
    old = []
    for d in os.listdir(ROOT):
        p = os.path.join(ROOT, d)
        if d == cache.key or not os.path.isdir(p): continue
        try: meta = json.load(open(os.path.join(p, 'meta.json'), encoding='utf-8'))
        except Exception: continue
        if meta.get('path') == cache.path: old.append((os.path.getmtime(p), p))
    for _, p in sorted(old, reverse=True)[keep:]: shutil.rmtree(p, ignore_errors=True)


# ---- host1 / host2
H2PY = '/home/user/h2/sp:/home/user/h2/sp2:/home/user/h2/sp3'     # host2 site dirs (numpy, shapely, ezdxf, numba wheels)
def warm_host1(files, a, host='host1'):
    """run warm on host1 (h1run), wait, pull the cache directories back, merge READY.json"""
    from rvtsheets.cache import Cache, ROOT, mark_ready
    for f in files:                                   # host1 has the corpus; copy other files to the same path
        if subprocess.run(['ssh', host, 'test -f %s' % shq(f)]).returncode:
            subprocess.run(['ssh', host, 'mkdir -p %s' % shq(os.path.dirname(f))], check=True)
            subprocess.run(['rsync', '-a', f, host + ':' + f], check=True)
    name = 'warm-%d' % os.getpid()
    runner = H1RUN if host == 'host1' else H1RUN.replace('h1run', 'h2run')
    pre = ['env', 'PYTHONPATH=' + H2PY] if host == 'host2' else []
    cmd = [runner, 'run', name, '--dir', REPO, '--'] + pre + ['python', '-m', 'rvtsheets.warm', '--mem', a.mem, '--port', str(a.port)] \
        + (['--workers', str(a.workers)] if a.workers else []) + (['--refresh'] if a.refresh else []) + files
    r = subprocess.run(cmd)
    if r.returncode: sys.exit('h1run could not start the job (exit %d)' % r.returncode)
    seen = 0
    while True:
        time.sleep(5)
        log = subprocess.run(['ssh', host, 'cat ~/offload/%s.log' % name], capture_output=True, text=True).stdout.splitlines()
        for l in log[seen:]: print('host1: ' + l, flush=True)
        seen = len(log)
        st = subprocess.run(['ssh', host, 'systemctl --user is-active %s-%s' % (host.replace('host', 'h'), name)], capture_output=True, text=True).stdout.strip()
        if st not in ('active', 'activating'): break
    ok = True
    for f in files:
        c = Cache(f)
        rel = os.path.relpath(c.dir, os.path.expanduser('~'))
        if subprocess.run([runner, 'pull', rel]).returncode: print('could not pull %s' % rel); ok = False; continue
        try: s = c.doc(); fl = json.loads(c.read('failed.json'))
        except Exception: print('%s: not warmed on host1 (see the log above)' % f); ok = False; continue
        mark_ready(c, s, 0, a.port, failed=len(fl)); prune_old(c)
    return ok


def shq(s):
    import shlex
    return shlex.quote(s)


def in_scope():
    """already capped: inside an h1run unit on host1"""
    try: return '/h1-' in open('/proc/self/cgroup').read()
    except Exception: return False


def main():
    ap = argparse.ArgumentParser(prog='rvt-sheets warm', description=__doc__.split('\n')[0])
    ap.add_argument('files', nargs='+'); ap.add_argument('--workers', type=int); ap.add_argument('--mem', default='3G')
    ap.add_argument('--host1', action='store_true'); ap.add_argument('--host2', action='store_true'); ap.add_argument('--port', type=int, default=8810)
    ap.add_argument('--refresh', action='store_true'); a = ap.parse_args()
    files = [os.path.abspath(f) for f in a.files]
    for f in files:
        if not os.path.exists(f): sys.exit('no such file: %s' % f)
    sys.path.insert(0, REPO)
    if a.host1 or a.host2:
        ok = warm_host1(files, a, 'host2' if a.host2 else 'host1')
        print_summary(files)
        sys.exit(0 if ok else 1)
    mem = parse_mem(a.mem)
    if not os.environ.get('RVT_SHEETS_SCOPED') and shutil.which('systemd-run') and not in_scope():
        # cap the whole job (this process + workers); nice so the daily driver stays responsive
        os.environ['RVT_SHEETS_SCOPED'] = '1'
        cmd = ['systemd-run', '--user', '--scope', '--quiet', '-p', 'MemoryMax=%dM' % mem, '-p', 'MemorySwapMax=0', '-E', 'RVT_SHEETS_SCOPED=1',
               'nice', '-n', '19', sys.executable, '-m', 'rvtsheets.warm'] + sys.argv[1:]
        r = subprocess.run(cmd, cwd=REPO)
        if r.returncode in (0, 1): sys.exit(r.returncode)
        print('(systemd scope unavailable: exit %d, running uncapped with 1 worker)' % r.returncode)
        a.workers = 1
    tot_s = tot_v = 0; allfail = {}
    for f in files:
        try:
            ns, nv, failed, secs = warm_file(f, a.workers, mem, a.port, out=lambda l: print(l, flush=True), refresh=a.refresh)
        except Exception as ex:
            import traceback; traceback.print_exc()
            print('%s: FAILED %s: %s' % (f, type(ex).__name__, ex), flush=True); allfail[f] = str(ex); continue
        tot_s += ns; tot_v += nv
        if failed: allfail[f] = failed
        print('%s: %d sheets, %d views in %.0f s%s' % (os.path.basename(f), ns, nv, secs, ', %d failed' % len(failed) if failed else ''), flush=True)
    print_summary(files)
    print('warmed %d sheets, %d views' % (tot_s, tot_v), flush=True)
    sys.exit(1 if allfail else 0)


def print_summary(files):
    from rvtsheets.cache import ROOT
    try: ready = json.load(open(os.path.join(ROOT, 'READY.json'), encoding='utf-8'))
    except Exception: return
    print('READY (%s):' % os.path.join(ROOT, 'READY.json'))
    for f in files:
        r = ready.get(f)
        if r: print('  %s: %d sheets, %d views%s, prepared %s\n    demo: %s' % (os.path.basename(f), r['sheets'], r['views'],
                    ', %d FAILED' % r['failed'] if r.get('failed') else '', r['prepared'], r['demo']))


if __name__ == '__main__': main()
