"""aiohttp sub-application serving sheets and 2D views as SVG.
Mount in another aiohttp app:   app.add_subapp('/sheets/', make_app(resolver))   where resolver(mid) -> path of the .rvt for model id `mid`
Standalone:                     ./rvt-sheets serve FILE.rvt [--port 8810]   (model id 'local'; prints the URL, opens nothing)
Routes (relative to the mount point):
  GET  /                         page (web/index.html): sheet + view browser, SVG viewer with pan/zoom, progress card while loading
  GET  /api/{mid}/status         {'state': loading|ready|error, 'stage', 'percent', 'error'}; starts loading on first call
  GET  /api/{mid}/doc.json       sheets (number, name, viewports) and drawable views (id, name, kind, scale); 202 while loading
  GET  /api/{mid}/sheet/{id}.svg full sheet (title block, viewports, titles)
  GET  /api/{mid}/view/{id}.svg  one view at its scale
Artefacts are cached persistently by rvtsheets.cache (content hash of the file + reader version + rvtsheets version); cached SVGs are served
from disk with ETag (and immutable Cache-Control when requested with ?v=<key>), without decoding the model.
  GET  /api/{mid}/thumb/{sheet|view}/{id}.png  320 px thumbnail of a cached drawing
  GET  /api/{mid}/sheet/{id}.pdf, /api/{mid}/sheets.pdf   PDF of one sheet / all sheets (rsvg-convert, vector)
  GET  /api/{mid}/cache.json     {cached, sheets, total, views, views_total, key, failed, stale, current_key}: what `rvt-sheets warm` prepared
                                (no decoding); stale = an older complete cache is served because the current code/reader has none"""
import os, sys, json, hashlib, asyncio, glob, functools, threading, time, traceback
from aiohttp import web

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(os.path.dirname(HERE), 'web')
CACHE = os.environ.get('RVT_SHEETS_CACHE', os.path.expanduser('~/.cache/rvt-sheets'))
from .drawings import Model, render, DRAWABLE


class _Drawer:
    """one drawing job at a time (memory), page requests before background prefetches (priority 0 < 1)"""
    def __init__(self):
        import queue, itertools
        self.q = queue.PriorityQueue(); self.n = itertools.count(); self.t = None

    def _loop(self):
        while True:
            _, _, fn, loop, fut = self.q.get()
            if fut.cancelled(): continue
            try: r = fn(); loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(r))
            except BaseException as ex: loop.call_soon_threadsafe(lambda ex=ex: fut.done() or fut.set_exception(ex))

    async def run(self, prio, fn, *a):
        if self.t is None: self.t = threading.Thread(target=self._loop, daemon=True); self.t.start()
        loop = asyncio.get_running_loop(); fut = loop.create_future()
        self.q.put((prio, next(self.n), functools.partial(fn, *a), loop, fut))
        return await fut


_pool = _Drawer()


def code_stamp():
    h = hashlib.md5()
    for f in sorted(glob.glob(os.path.join(HERE, '*.py'))): h.update(open(f, 'rb').read())
    return h.hexdigest()[:8]


def error_svg(msg):
    import html
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="40mm" viewBox="0 0 200 40"><rect width="100%" height="100%" fill="#fff"/>'
            '<text x="5" y="20" font-family="sans-serif" font-size="5" fill="#b00">could not draw: %s</text></svg>' % html.escape(msg[:150]))


def make_app(resolver):
    models = {}

    def model(mid):
        if mid not in models:
            p = resolver(mid)
            if not p or not os.path.exists(p): raise web.HTTPNotFound(text='unknown model %s' % mid)
            models[mid] = Model(p, allow_stale=True)
        return models[mid]


    async def index(req): return web.FileResponse(os.path.join(WEB, 'index.html'))

    async def status(req): return web.json_response(model(req.match_info['mid']).status())

    async def doc(req):
        m = model(req.match_info['mid']); st = m.status()
        if st['state'] != 'ready': return web.json_response(st, status=202 if st['state'] == 'loading' else 500)
        return web.json_response(m.summary())

    async def drawing(req, kind):
        m = model(req.match_info['mid']); eid = int(req.match_info['id'])
        if m.status()['state'] != 'ready': return web.Response(text=error_svg('model not loaded yet'), content_type='image/svg+xml', status=202)
        etag = '"%s-%s-%d"' % (m.key, kind, eid)
        if m.is_cached(kind, eid):
            if req.headers.get('If-None-Match') == etag: return web.Response(status=304, headers={'ETag': etag})
            hdr = {'ETag': etag, 'X-Rvt-Cache': 'hit', 'Cache-Control': 'public, max-age=31536000, immutable' if req.query.get('v') == m.key else 'no-cache'}
            return web.FileResponse(m.cache.fn('%s_%d.svg' % (kind, eid)), headers=dict(hdr, **{'Content-Type': 'image/svg+xml'}))
        try: s = await _pool.run(1 if req.query.get('prefetch') else 0, m.svg, kind, eid); hdr = {'ETag': etag, 'X-Rvt-Cache': 'miss'}
        except Exception as ex:
            traceback.print_exc(); s = error_svg('%s %s: %s: %s' % (kind, eid, type(ex).__name__, ex)); hdr = {}
        return web.Response(text=s, content_type='image/svg+xml', headers=hdr)

    async def scene_json(req):
        """/api/{mid}/view/{id}.json?scale=&detail=&template=0&filters=0&cut=&phase=&phaseFilter= : view primitives for the viewer's control panel (CONTROL-API.md)"""
        from .drawings import scene_text
        m = model(req.match_info['mid']); vid = int(req.match_info['id'])
        if m.status()['state'] != 'ready': return web.json_response(m.status(), status=202)
        q = req.query; opts = {}
        for k in ('scale', 'detail', 'phase', 'phaseFilter'):
            if q.get(k) not in (None, ''): opts[k] = int(q[k])
        if q.get('cut') not in (None, ''): opts['cut'] = float(q['cut'])
        for k in ('template', 'filters'):
            if q.get(k) in ('0', 'false'): opts[k] = False
        try: txt = await _pool.run(0, scene_text, m, vid, opts)
        except KeyError: raise web.HTTPNotFound(text='unknown view %d' % vid)
        except Exception as ex:
            traceback.print_exc(); return web.json_response({'error': '%s: %s' % (type(ex).__name__, ex)}, status=500)
        return web.Response(text=txt, content_type='application/json', headers={'X-Rvt-Cache-Key': m.key})

    async def vg_json(req):
        """/api/{mid}/view/{id}/vg.json[?full=1] : graphics resolution of a view for the hidden-line renderer / control panel (CONTROL-API.md 'Graphics resolution')"""
        from .drawings import vg_text
        m = model(req.match_info['mid']); vid = int(req.match_info['id'])
        if m.status()['state'] != 'ready': return web.json_response(m.status(), status=202)
        try: txt = await _pool.run(0, vg_text, m, vid, req.query.get('full') == '1')
        except KeyError: raise web.HTTPNotFound(text='unknown view %d' % vid)
        except Exception as ex:
            traceback.print_exc(); return web.json_response({'error': '%s: %s' % (type(ex).__name__, ex)}, status=500)
        return web.Response(text=txt, content_type='application/json', headers={'X-Rvt-Cache-Key': m.key})

    async def cache_json(req):
        """cache state without decoding: {cached, sheets, total, views, views_total, key, failed}"""
        m = model(req.match_info['mid'])
        d = m._summary
        if d is None: return web.json_response({'cached': False, 'sheets': 0, 'total': None, 'views': 0, 'views_total': None, 'key': m.key, 'stale': False})
        cs = sum(1 for x in d['sheets'] if m.is_cached('sheet', x['id'])); cv = sum(1 for x in d['views'] if m.is_cached('view', x['id']))
        try: failed = len(json.loads(m.cache.read('failed.json')))
        except Exception: failed = None
        return web.json_response({'cached': cs == len(d['sheets']) and cv == len(d['views']), 'sheets': cs, 'total': len(d['sheets']),
                                  'views': cv, 'views_total': len(d['views']), 'key': m.key, 'failed': failed,
                                  'stale': m.stale, 'current_key': m.current_key})

    async def pdf(req):
        """one sheet (/sheet/{id}.pdf) or every sheet (/sheets.pdf) as PDF; drawings not cached yet are rendered first"""
        from .pdf import model_pdf
        m = model(req.match_info['mid'])
        if m.status()['state'] != 'ready': raise web.HTTPServiceUnavailable(text='model not loaded yet')
        if 'id' in req.match_info: ids = [int(req.match_info['id'])]; name = 'sheet_%d.pdf' % ids[0]
        else: ids = [x['id'] for x in m._summary['sheets']]; name = 'sheets.pdf'
        if not ids: raise web.HTTPNotFound(text='no sheets in this file')
        fn = m.cache.fn(name)
        if not m.cache.has(name): await _pool.run(0, model_pdf, m, ids, fn)
        base = os.path.splitext(os.path.basename(m.path))[0]
        nice = '%s - %s.pdf' % (base, next((str(x['number']) for x in m._summary['sheets'] if x['id'] == ids[0]), ids[0])) if len(ids) == 1 else base + ' - sheets.pdf'
        return web.FileResponse(fn, headers={'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename="%s"' % nice.replace('"', '')})

    async def thumb(req):
        m = model(req.match_info['mid']); kind = req.match_info['kind']; eid = int(req.match_info['id'])
        fn = await asyncio.get_running_loop().run_in_executor(None, m.cache.thumb, kind, eid)
        if not fn: raise web.HTTPNotFound()
        return web.FileResponse(fn, headers={'Cache-Control': 'public, max-age=31536000, immutable' if req.query.get('v') == m.key else 'no-cache'})

    app = web.Application()
    app.router.add_get('/', index)
    app.router.add_get('/api/{mid}/status', status)
    app.router.add_get('/api/{mid}/doc.json', doc)
    app.router.add_get('/api/{mid}/sheet/{id}.svg', lambda r: drawing(r, 'sheet'))
    app.router.add_get('/api/{mid}/view/{id}.svg', lambda r: drawing(r, 'view'))
    app.router.add_get('/api/{mid}/view/{id}.json', scene_json)
    app.router.add_get('/api/{mid}/view/{id}/vg.json', vg_json)
    app.router.add_get('/api/{mid}/thumb/{kind}/{id}.png', thumb)
    app.router.add_get('/api/{mid}/cache.json', cache_json)
    app.router.add_get('/api/{mid}/sheet/{id}.pdf', pdf)
    app.router.add_get('/api/{mid}/sheets.pdf', pdf)
    app.router.add_static('/static/', WEB, follow_symlinks=False)
    app['preload'] = lambda mid: model(mid).start()
    return app


def main():
    import argparse
    ap = argparse.ArgumentParser(prog='rvt-sheets serve'); ap.add_argument('file'); ap.add_argument('--port', type=int, default=8810)
    ap.add_argument('--host', default='127.0.0.1'); a = ap.parse_args()
    path = os.path.abspath(a.file)
    if not os.path.exists(path): sys.exit('no such file: %s' % path)
    root = web.Application(); app = make_app(lambda mid: path); root.add_subapp('/sheets/', app)
    async def go(req): raise web.HTTPFound('/sheets/#local')
    root.router.add_get('/', go)
    app['preload']('local')                       # start reading right away; the page shows progress
    print('rvt-sheets: %s\n  open http://%s:%d/sheets/#local   (Ctrl-C to stop)' % (path, a.host, a.port), flush=True)
    web.run_app(root, host=a.host, port=a.port, print=None)


if __name__ == '__main__': main()
