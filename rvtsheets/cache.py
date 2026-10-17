"""Persistent artefact cache: ~/.cache/rvt-sheets/<key>/ with
  doc.json            sheet/view summary (+ which artefacts exist)
  sheet_<id>.svg      full sheets           view_<id>.svg   views
  thumb_<kind>_<id>.png  320 px thumbnails  meta.json       file, key parts, timings
key = sha1(file content sha1 | rvtsheets drawing-code version | SETTINGS_VERSION): any change of the file or of this package's drawing code
gives a new directory (old ones can be deleted freely; warm prunes them). The reader version (~/rvt-research rvt*.py, g103_get.py, json
tables) is recorded in meta.json but is NOT part of the key: the reader is edited many times a day by another session and a demo cache must
survive that; `rvt-sheets warm --refresh` redraws with the current reader.
~/.cache/rvt-sheets/READY.json lists prepared files (warm)."""
import os, json, glob, hashlib, time, subprocess, shutil

ROOT = os.environ.get('RVT_SHEETS_CACHE', os.path.expanduser('~/.cache/rvt-sheets'))
HERE = os.path.dirname(os.path.abspath(__file__))
READER_DIR = os.environ.get('RVT_READER_DIR', os.path.expanduser('~/rvt-research'))
SETTINGS_VERSION = '1'          # bump when output-affecting settings change (pixel sizes, tolerances...)


def _hash_files(files):
    h = hashlib.sha1()
    for f in sorted(files):
        try: h.update(os.path.basename(f).encode()); h.update(open(f, 'rb').read())
        except OSError: pass
    return h.hexdigest()[:12]


NOT_DRAWING = {'server.py', 'warm.py', 'cache.py', 'drawings.py', 'pdf.py', '__init__.py'}     # serving code: changing it keeps the cache


def code_version():
    return _hash_files([f for f in glob.glob(os.path.join(HERE, '*.py')) + glob.glob(os.path.join(HERE, 'vg', '*.py')) if os.path.basename(f) not in NOT_DRAWING]
                       + glob.glob(os.path.join(HERE, 'data', '*.json')))


def reader_version():
    return _hash_files(glob.glob(os.path.join(READER_DIR, 'rvt*.py')) + glob.glob(os.path.join(READER_DIR, 'g103_get.py'))
                       + glob.glob(os.path.join(READER_DIR, '*_names.json')))


def file_hash(path):
    """content sha1, memoised per (path, size, mtime) in ROOT/filehash.json"""
    os.makedirs(ROOT, exist_ok=True)
    idx_fn = os.path.join(ROOT, 'filehash.json')
    try: idx = json.load(open(idx_fn))
    except Exception: idx = {}
    st = os.stat(path); k = '%s|%d|%d' % (os.path.abspath(path), st.st_size, int(st.st_mtime))
    if k in idx: return idx[k]
    h = hashlib.sha1()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 22), b''): h.update(b)
    idx[k] = h.hexdigest()
    tmp = idx_fn + '.%d' % os.getpid(); json.dump(idx, open(tmp, 'w')); os.replace(tmp, idx_fn)
    return idx[k]


class Cache:
    def __init__(self, path, key=None):
        """key: reuse a known cache directory (warm workers keep their parent's key even if the code changes meanwhile)"""
        self.path = os.path.abspath(path)
        self.parts = {'file': file_hash(self.path), 'code': code_version(), 'settings': SETTINGS_VERSION}
        self.key = key or hashlib.sha1(json.dumps(self.parts, sort_keys=True).encode()).hexdigest()[:16]
        self.parts['reader'] = reader_version()
        self.dir = os.path.join(ROOT, self.key); os.makedirs(self.dir, exist_ok=True)
        if not self.has('meta.json'): self.write('meta.json', json.dumps({'path': self.path, 'parts': self.parts, 'created': time.strftime('%Y-%m-%d %H:%M:%S')}))

    def fn(self, name): return os.path.join(self.dir, name)
    def has(self, name): return os.path.exists(self.fn(name))
    def read(self, name, mode='r'): return open(self.fn(name), mode).read()

    def write(self, name, data):
        tmp = self.fn(name) + '.%d.tmp' % os.getpid()
        with open(tmp, 'wb' if isinstance(data, bytes) else 'w') as fh: fh.write(data)
        os.replace(tmp, self.fn(name))

    def doc(self):
        try: return json.loads(self.read('doc.json'))
        except Exception: return None

    def thumb(self, kind, eid, width=320):
        """PNG thumbnail of a cached SVG (rsvg-convert); None when unavailable"""
        src = self.fn('%s_%d.svg' % (kind, eid)); dst = 'thumb_%s_%d.png' % (kind, eid)
        if self.has(dst): return self.fn(dst)
        if not os.path.exists(src) or not shutil.which('rsvg-convert'): return None
        try:
            subprocess.run(['rsvg-convert', '-w', str(width), '-b', 'white', src, '-o', self.fn(dst) + '.tmp'], check=True, timeout=120, capture_output=True)
            os.replace(self.fn(dst) + '.tmp', self.fn(dst)); return self.fn(dst)
        except Exception: return None


def best_complete(path, file_sha=None):
    """newest COMPLETE cache directory of this file content (any drawing-code / reader version): key or None. Complete = warm finished
    (complete.json) or, for caches warmed before that marker existed, READY.json lists the key with no failed drawing. Lets the server open
    at once after a code or reader change instead of rendering on the demo machine (c2-viewer request, HOOKS.md 2026-10-15)."""
    path = os.path.abspath(path); sha = file_sha or file_hash(path)
    try: ready = json.load(open(os.path.join(ROOT, 'READY.json'))).get(path) or {}
    except Exception: ready = {}
    best = None
    for d in os.listdir(ROOT) if os.path.isdir(ROOT) else []:
        p = os.path.join(ROOT, d)
        try: meta = json.load(open(os.path.join(p, 'meta.json')))
        except Exception: continue
        if meta.get('path') != path or (meta.get('parts') or {}).get('file') != sha or not os.path.exists(os.path.join(p, 'doc.json')): continue
        c = os.path.join(p, 'complete.json')
        if os.path.exists(c): t = os.path.getmtime(c)
        elif ready.get('key') == d and not ready.get('failed'): t = os.path.getmtime(os.path.join(p, 'doc.json'))
        else: continue
        if best is None or t > best[0]: best = (t, d)
    return best[1] if best else None


def mark_ready(cache, summary, seconds, port=8810, failed=0):
    cache.write('complete.json', json.dumps({'failed': failed, 'prepared': time.strftime('%Y-%m-%d %H:%M:%S'), 'parts': cache.parts}))
    fn = os.path.join(ROOT, 'READY.json')
    try: ready = json.load(open(fn))
    except Exception: ready = {}
    ready[cache.path] = {'key': cache.key, 'parts': cache.parts, 'sheets': len(summary['sheets']), 'views': len(summary['views']),
                         'failed': failed, 'warm_seconds': round(seconds, 1), 'prepared': time.strftime('%Y-%m-%d %H:%M:%S'),
                         'demo': '%s %s --sheets' % (os.path.expanduser('~/src/rvt-viewer/bin/rvt-view'), cache.path),
                         'standalone': '%s serve %s --port %d' % (os.path.join(os.path.dirname(HERE), 'rvt-sheets'), cache.path, port)}
    tmp = fn + '.%d' % os.getpid(); json.dump(ready, open(tmp, 'w'), indent=1); os.replace(tmp, fn)
