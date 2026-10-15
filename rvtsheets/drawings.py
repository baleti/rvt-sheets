"""Model: one .rvt file = persistent artefact cache (rvtsheets.cache) + lazy decoder; render(): draw one sheet/view.
Shared by the server and by warm (no aiohttp needed here)."""
import os, sys, json, threading, time, traceback

DRAWABLE = ('plan', 'section', 'drafting', 'legend', '3d')


class Model:
    """one .rvt: persistent artefact cache (rvtsheets.cache) + lazy decoder; when doc.json and the requested SVGs are cached nothing is decoded"""
    def __init__(self, path, allow_stale=False):
        """allow_stale (server, PDF): when the current key has no complete cache, use the newest complete cache of the same file content
        (older drawing code / reader) and say so (self.stale); `warm` always fills the current key"""
        from .cache import Cache, best_complete
        self.path = path; self._dec = None; self._doc = None; self._drawer = None
        self.size = os.stat(path).st_size
        self.cache = Cache(path); self.current_key = self.cache.key; self.stale = False
        if allow_stale and not self.cache.has('complete.json'):
            k = best_complete(path, self.cache.parts['file'])
            if k and k != self.cache.key: self.cache = Cache(path, k); self.stale = True
        self.key = self.cache.key; self.dir = self.cache.dir
        self.state = 'idle'; self.stage = ''; self.t0 = None; self.error = None; self.lock = threading.Lock()
        self._summary = self.cache.doc()
        if self._summary is not None: self.state = 'ready'; self.stage = 'ready (cached)'; self.t0 = self.t_ready = time.time()
        self.expected = self._expected_seconds()
        self.decode_lock = threading.Lock()

    def _expected_seconds(self):
        """reader decode time estimate (first open; later opens hit the reader cache): ~1.5 s per MB, measured on the corpus"""
        try: return float(self.cache.read('load_seconds'))
        except Exception: return max(5.0, self.size / 1e6 * 1.5)

    def start(self):
        with self.lock:
            if self.state != 'idle': return
            self.state = 'loading'; self.t0 = time.time()
        threading.Thread(target=self._load, daemon=True).start()

    def decoder(self):
        """decode on demand (cache miss): reader records -> doc -> drawer"""
        with self.decode_lock:
            if self._doc is None:
                self.stage = 'reading the .rvt (records, graphics index)'
                from .decode import Decoder
                from .viewdraw import ViewDrawer
                self._dec = Decoder(self.path)
                self.stage = 'decoding views, sheets, styles'
                self._doc = self._dec.doc(); self._drawer = ViewDrawer(self._dec, self._doc)
        return self._dec, self._doc

    def _load(self):
        try:
            self.decoder()
            self._summary = self._make_summary()
            self.cache.write('doc.json', json.dumps(self._summary))
            self.cache.write('load_seconds', '%.1f' % (time.time() - self.t0))
            self.t_ready = time.time(); self.state = 'ready'; self.stage = 'ready'
        except Exception as ex:
            self.error = '%s: %s' % (type(ex).__name__, ex); self.trace = traceback.format_exc(); self.state = 'error'
            print('rvt-sheets: load failed for %s\n%s' % (self.path, self.trace), file=sys.stderr)

    def status(self):
        self.start()
        pct = 100 if self.state == 'ready' else min(95, int(100 * (time.time() - (self.t0 or time.time())) / max(self.expected, 1)))
        return {'state': self.state, 'stage': self.stage, 'percent': pct, 'error': self.error, 'file': os.path.basename(self.path),
                'elapsed': round((getattr(self, 't_ready', None) or time.time()) - (self.t0 or time.time()), 1), 'key': self.key}

    def _make_summary(self):
        doc = self._doc
        sheets = [{'id': s['id'], 'number': s.get('sheetNumber'), 'name': s.get('name'),
                   'views': [vp['view'] for vp in s['viewports'] if vp['view'] in doc['views']]} for s in doc['sheets'].values()]
        views = [{'id': v['id'], 'name': v['name'], 'kind': v['kind'], 'scale': v.get('scale') if v['kind'] != '3d' or v.get('scale', 0) > 1 else None}
                 for v in doc['views'].values() if not v.get('template') and v.get('kind') in DRAWABLE and v.get('name') and not v.get('error')]
        return {'file': os.path.basename(self.path), 'sheets': sorted(sheets, key=lambda s: str(s['number'])),
                'views': sorted(views, key=lambda v: (v['kind'], v['name']))}

    def summary(self):
        s = dict(self._summary); s['key'] = self.key
        s['sheets'] = [dict(x, cached=self.cache.has('sheet_%d.svg' % x['id'])) for x in s['sheets']]
        s['views'] = [dict(x, cached=self.cache.has('view_%d.svg' % x['id'])) for x in s['views']]
        return s

    def is_cached(self, kind, eid): return self.cache.has('%s_%d.svg' % (kind, eid))

    def svg(self, kind, eid):
        name = '%s_%d.svg' % (kind, eid)
        if self.cache.has(name): return self.cache.read(name)
        s = render(self, kind, eid)
        self.cache.write(name, s)
        return s


def render(m, kind, eid):
    """draw one artefact with a model's decoder (used by the server and by warm)"""
    dec, doc = m.decoder() if hasattr(m, 'decoder') else m
    drawer = m._drawer
    if kind == 'sheet':
        from .compose import sheet_svg
        return sheet_svg(dec, eid, doc, drawer, log=lambda *a: None)
    from .viewsvg import view_svg
    v = doc['views'][eid]
    from . import shaded3d
    if shaded3d.is_shaded(v):
        try:
            sv = shaded3d.view_svg(drawer, eid)
            if sv: return sv
        except Exception: pass                                # fall back to the line drawing
    from .compose import crop_rect_uv
    return view_svg(drawer.draw(eid), v.get('scale') or 100, crop=crop_rect_uv(v))
