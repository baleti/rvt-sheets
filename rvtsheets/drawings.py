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


# ---- view scene JSON (control API: c2-vctl / c2-annot, CONTROL-API.md)
SCENE_KEEP = ('t', 'elem', 'layer', 'pts', 'segs', 'loops', 'style', 'fill', 'color', 'text', 'origin', 'x', 'size', 'font', 'bold', 'italic', 'halign', 'valign', 'anchor',
              'box', 'order', 'cat', 'elems', 'part', 'paper', 'gs', 'pattern', 'hang', 'host')


PROP_CLASSES = {'IndependentTag', 'RoomTag', 'SpaceTag', 'AreaTag', 'TextNote', 'LinearDimString', 'SpotElevation', 'Grid', 'Level', 'Section', 'InteriorElev', 'StairsPathElement'}


def _rnd(x, n=4):
    if isinstance(x, float): return round(x, n)
    if isinstance(x, (list, tuple)): return [_rnd(a, n) for a in x]
    if hasattr(x, 'tolist'): return _rnd(x.tolist(), n)
    return x


def scene_name(vid, opts):
    import hashlib
    k = json.dumps({a: opts.get(a) for a in sorted(opts) if opts.get(a) is not None}, sort_keys=True)
    return 'scene_%d_%s.json' % (vid, hashlib.sha1(k.encode()).hexdigest()[:10])


def scene(m, vid, opts):
    """view drawing as JSON primitives (view coordinates, model feet, sizes x scale) with the element table; opts: scale (annotation scale 1:N), detail (1-3),
    template (False = ignore the view template), filters (False = ignore view filters), cut (absolute cut plane elevation, ft), phase, phaseFilter.
    The same shape as rvtviewer/vscene_worker.py's scene. Draws with the model's drawer: call from the single drawing thread."""
    dec, doc = m.decoder(); d = m._drawer; vis = d.vis
    v0 = doc['views'][vid]; saved_scale = v0.get('scale'); eff0 = vis.effective; saved_range = v0.get('range'); saved_phase = (v0.get('phase'), v0.get('phase_filter'))
    t0 = time.time()
    try:
        if opts.get('scale'): v0['scale'] = int(opts['scale'])
        if opts.get('cut') is not None and saved_range: v0['range'] = dict(saved_range, cut=float(opts['cut']))
        if opts.get('phase') is not None: v0['phase'] = int(opts['phase'])
        if opts.get('phaseFilter') is not None: v0['phase_filter'] = int(opts['phaseFilter'])

        def eff(v):
            e = dict(eff0(v) if opts.get('template', True) is not False else v)
            if opts.get('detail'): e['detail_level'] = int(opts['detail'])
            if opts.get('filters') is False: e['filters'] = None; e['draw_filters'] = None
            if opts.get('phaseFilter') is not None: e['phase_filter'] = int(opts['phaseFilter'])
            return e
        vis.effective = eff
        dr = d.draw(vid)
    finally:
        v0['scale'] = saved_scale; vis.effective = eff0; v0['range'] = saved_range; v0['phase'], v0['phase_filter'] = saved_phase
    info = vis.info.info; cats = doc['categories']; els = {}
    for p in dr['prims']:
        e = p.get('elem')
        if e is None or e in els: continue
        i = info.get(e) or {}; c = i.get('cat'); cc = cats.get(c) or {}
        par = cc.get('parent'); pn = (cats.get(par) or {}).get('name') if par not in (None, -1) else None
        els[e] = {'cls': i.get('cls'), 'cat': c, 'catName': cc.get('name'), 'parent': par if par not in (None, -1) else None, 'parentName': pn}
        if i.get('cls') in PROP_CLASSES:
            try: els[e].update(d.tags.element_props(e))
            except Exception: pass
        txt = [q['text'] for q in dr['prims'] if q.get('elem') == e and q.get('t') == 'text' and q.get('text')] if i.get('cls') in PROP_CLASSES else None
        if txt: els[e]['text'] = '\n'.join(txt)
    prims = [{k: _rnd(p[k]) for k in SCENE_KEEP if k in p and p[k] is not None} for p in dr['prims'] if p.get('t') != 'image']
    vw = {k: _rnd(v0.get(k)) for k in ('id', 'name', 'kind', 'scale', 'origin', 'right', 'up', 'dir', 'range', 'discipline', 'detail_level', 'view_template')}
    cr = v0.get('crop') or {}
    vw['crop'] = {k: _rnd(cr.get(k)) for k in ('origin', 'basis', 'bounds', 'active', 'crop_active', 'annotation_crop_active')} if cr else None
    vw['scale_stored'] = saved_scale; vw['scale'] = int(opts['scale']) if opts.get('scale') else saved_scale
    try:
        from .compose import crop_rect_uv
        vw['crop_uv'] = _rnd(crop_rect_uv(v0))
    except Exception: vw['crop_uv'] = None
    return {'view': vw, 'prims': prims, 'elements': {str(k): v for k, v in els.items()}, 'options': opts, 'stats': dr.get('stats'),
            'seconds': round(time.time() - t0, 1), 'key': m.key}


def scene_text(m, vid, opts):
    """cached scene JSON text (cache file next to the SVGs, same key)"""
    name = scene_name(vid, opts)
    if m.cache.has(name): return m.cache.read(name)
    def j(o):
        if hasattr(o, 'tolist'): return o.tolist()
        if isinstance(o, (set, tuple)): return list(o)
        return str(o)
    s = json.dumps(scene(m, vid, opts), default=j, separators=(',', ':'))
    m.cache.write(name, s)
    return s
