"""HTTP contracts with synthetic models, real disk caching, and no Revit reader."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType

import pytest
from aiohttp import BaseConnector, ClientTimeout, web, web_fileresponse
from yarl import URL
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rvtsheets import cache, drawings, server


SVG = '<svg xmlns="http://www.w3.org/2000/svg"><text>synthetic drawing</text></svg>'
PDF = b'%PDF-1.4\n% synthetic PDF route fixture\n%%EOF\n'
SUMMARY = {
    'file': 'model.xrt',
    'sheets': [{'id': 1, 'number': 'A101', 'name': 'Ground floor', 'views': [42]}],
    'views': [{'id': 42, 'name': 'Floor plan', 'kind': 'plan', 'scale': 100}],
}
CACHE_FIELDS = {'cached', 'sheets', 'total', 'views', 'views_total', 'key',
                'failed', 'stale', 'current_key'}


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(web_fileresponse, 'NOSENDFILE', True)
    root = tmp_path / 'cache'
    code = tmp_path / 'code'
    reader = tmp_path / 'reader'
    code.mkdir()
    reader.mkdir()
    monkeypatch.setenv('RVT_SHEETS_CACHE', str(root))
    monkeypatch.setenv('RVT_READER_DIR', str(reader))
    monkeypatch.setattr(cache, 'ROOT', str(root))
    monkeypatch.setattr(cache, 'HERE', str(code))
    monkeypatch.setattr(cache, 'READER_DIR', str(reader))
    monkeypatch.setattr(server, 'CACHE', str(root))

    # This source-only checkout has no web assets. Test FileResponse routing
    # against a stand-in; test_packaged_main_page records the missing real page.
    assets = tmp_path / 'web'
    assets.mkdir()
    (assets / 'index.html').write_text('<!doctype html><title>rvt-sheets</title>')
    monkeypatch.setattr(server, 'WEB', str(assets))
    path = tmp_path / 'model.xrt'
    path.write_bytes(b'synthetic model, not a Revit file')
    model = drawings.Model(str(path))
    renders = []
    pdf_calls = []

    # Keep the real Model summary/svg methods and Cache, but never start a
    # loader thread or import the external decoder/rendering dependencies.
    def start(self):
        if self.state == 'idle':
            self.state = self.stage = 'ready'
            self._summary = json.loads(json.dumps(SUMMARY))
            self.cache.write('doc.json', json.dumps(self._summary))

    def render(model, kind, eid):
        known = {'sheet': {1}, 'view': {42}}
        if eid not in known[kind]:
            raise KeyError(eid)
        renders.append((kind, eid))
        return SVG

    def make_model(filename, allow_stale=False):
        assert filename == str(path)
        assert allow_stale is True
        return model

    class InlineDrawer:
        async def run(self, priority, fn, *args):
            return fn(*args)

    # pdf.py is absent here; supply only its rendering boundary. The route
    # must still choose the ids, cache the output and serve it over HTTP.
    pdf_module = ModuleType('rvtsheets.pdf')

    def model_pdf(model, ids, filename):
        pdf_calls.append(ids)
        Path(filename).write_bytes(PDF)

    pdf_module.model_pdf = model_pdf
    monkeypatch.setitem(sys.modules, 'rvtsheets.pdf', pdf_module)
    monkeypatch.setattr(drawings.Model, 'start', start)
    monkeypatch.setattr(drawings, 'render', render)
    monkeypatch.setattr(server, 'Model', make_model)
    monkeypatch.setattr(server, '_pool', InlineDrawer())

    def app(mounted=False):
        child = server.make_app(lambda mid: str(path) if mid == 'local' else None)
        if not mounted:
            return child
        parent = web.Application()
        parent.add_subapp('/sheets/', child)
        return parent

    return SimpleNamespace(model=model, app=app, renders=renders, pdf_calls=pdf_calls)


class InMemoryTestServer(TestServer):
    """Run aiohttp HTTP protocols without binding a socket in the sandbox."""

    async def start_server(self, loop=None, **kwargs):
        if self.runner:
            return
        self._loop = loop
        self.runner = await self._make_runner(handler_cancellation=True, shutdown_timeout=0.1, **kwargs)
        await self.runner.setup()
        self._root = URL('http://localhost')


class MemoryTransport(asyncio.Transport):
    """Carry real HTTP bytes between aiohttp protocols without OS networking."""

    def __init__(self, protocol):
        super().__init__()
        self.protocol = protocol
        self.peer = None
        self.closing = False

    def is_closing(self):
        return self.closing

    def write(self, data):
        asyncio.get_running_loop().call_soon(self.peer.protocol.data_received, bytes(data))

    def writelines(self, lines):
        self.write(b''.join(lines))

    def get_write_buffer_size(self):
        return 0

    def close(self):
        if self.closing:
            return
        self.closing = self.peer.closing = True
        loop = asyncio.get_running_loop()
        loop.call_soon(self.protocol.connection_lost, None)
        loop.call_soon(self.peer.protocol.connection_lost, None)

    def abort(self):
        self.close()


class InMemoryConnector(BaseConnector):
    def __init__(self, test_server):
        super().__init__()
        self.test_server = test_server

    async def _create_connection(self, req, traces, timeout):
        client = self._factory()
        handler = self.test_server.runner.server()
        client_transport = MemoryTransport(client)
        server_transport = MemoryTransport(handler)
        client_transport.peer = server_transport
        server_transport.peer = client_transport
        handler.connection_made(server_transport)
        client.connection_made(client_transport)
        return client


async def exercise(harness, check, mounted=False):
    # FileResponse offloads tiny local reads. Execute those synchronously so
    # asyncio needs no thread-to-loop wakeup socket in this restricted runner.
    loop = asyncio.get_running_loop()
    def run_inline(executor, fn, *args):
        future = loop.create_future()
        try:
            future.set_result(fn(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future
    loop.run_in_executor = run_inline
    test_server = InMemoryTestServer(harness.app(mounted))
    async with TestClient(test_server, connector=InMemoryConnector(test_server), timeout=ClientTimeout(total=2)) as client:
        await check(client)


@pytest.mark.parametrize('mounted', [False, True])
def test_main_page_and_viewer_mount(harness, mounted):
    async def check(client):
        prefix = '/sheets' if mounted else ''
        response = await client.get(prefix + '/')
        assert response.status == 200
        assert response.content_type == 'text/html'
        assert 'rvt-sheets' in await response.text()
        response = await client.get(prefix + '/api/local/status')
        assert response.status == 200
        assert (await response.json())['state'] == 'ready'
        response = await client.get(prefix + '/api/local/sheet/1.svg')
        assert response.status == 200
        assert await response.text() == SVG
    asyncio.run(exercise(harness, check, mounted))


@pytest.mark.parametrize('state, code', [('ready', 200), ('error', 500), ('loading', 202)])
def test_status_and_doc(harness, state, code):
    model = harness.model
    model.start()
    model.state = state
    model.stage = state
    model.error = 'synthetic load failure' if state == 'error' else None

    async def check(client):
        response = await client.get('/api/local/status')
        assert response.status == 200
        status = await response.json()
        assert status['state'] == state
        assert status['stage'] == state
        assert status['error'] == model.error
        assert isinstance(status['percent'], int)
        if state == 'ready':
            assert status['percent'] == 100
        response = await client.get('/api/local/doc.json')
        assert response.status == code
        doc = await response.json()
        if state == 'ready':
            assert doc == dict(SUMMARY, key=model.key,
                               sheets=[dict(SUMMARY['sheets'][0], cached=False)],
                               views=[dict(SUMMARY['views'][0], cached=False)])
        else:
            assert doc['state'] == state
            assert doc['error'] == model.error
    asyncio.run(exercise(harness, check))


@pytest.mark.parametrize('warm, stale', [(False, False), (True, False), (True, True)])
def test_cache_with_summary(harness, warm, stale):
    model = harness.model
    model.start()
    model.stale = stale
    if stale:
        model.current_key = 'new-code-key'
    if warm:
        model.svg('sheet', 1)
        model.svg('view', 42)
        model.cache.write('failed.json', '[]')

    async def check(client):
        response = await client.get('/api/local/cache.json')
        assert response.status == 200
        data = await response.json()
        assert set(data) == CACHE_FIELDS
        assert data == {'cached': warm, 'sheets': int(warm), 'total': 1,
                        'views': int(warm), 'views_total': 1, 'key': model.key,
                        'failed': 0 if warm else None, 'stale': stale,
                        'current_key': model.current_key}
    asyncio.run(exercise(harness, check))


def test_cold_cache_without_summary(harness):
    async def check(client):
        response = await client.get('/api/local/cache.json')
        assert response.status == 200
        data = await response.json()
        expected = {'cached': False, 'sheets': 0, 'total': None, 'views': 0,
                    'views_total': None, 'key': harness.model.key, 'stale': False}
        assert {key: data[key] for key in expected} == expected
        assert harness.model._summary is None  # cache inspection never loads it
    asyncio.run(exercise(harness, check))


def test_cold_cache_has_all_documented_fields(harness):
    async def check(client):
        response = await client.get('/api/local/cache.json')
        assert response.status == 200
        assert CACHE_FIELDS <= (await response.json()).keys()
    asyncio.run(exercise(harness, check))


@pytest.mark.parametrize('kind, eid', [('sheet', 1), ('view', 42)])
def test_svg_miss_then_hit(harness, kind, eid):
    async def check(client):
        url = f'/api/local/{kind}/{eid}.svg'
        for expected in ('miss', 'hit'):
            response = await client.get(url)
            assert response.status == 200
            assert response.content_type == 'image/svg+xml'
            assert response.headers['X-Rvt-Cache'] == expected
            assert await response.text() == SVG
        assert harness.renders == [(kind, eid)]
        assert harness.model.cache.read(f'{kind}_{eid}.svg') == SVG
    asyncio.run(exercise(harness, check))


@pytest.mark.parametrize('suffix', ['status', 'doc.json', 'cache.json',
                                   'sheet/1.svg', 'view/42.svg', 'sheet/1.pdf'])
def test_unknown_model_is_404(harness, suffix):
    async def check(client):
        response = await client.get('/api/unknown/' + suffix)
        assert response.status == 404
    asyncio.run(exercise(harness, check))


@pytest.mark.parametrize('kind', ['sheet', 'view'])
@pytest.mark.xfail(strict=True, raises=AssertionError, reason='drawing() catches KeyError and serves an error SVG with HTTP 200')
def test_unknown_drawing_is_404(harness, kind):
    async def check(client):
        response = await client.get(f'/api/local/{kind}/999.svg')
        assert response.status == 404
    asyncio.run(exercise(harness, check))


@pytest.mark.parametrize('route', ['sheet/1.pdf', 'sheets.pdf'])
def test_pdf_content_type_and_cache(harness, route):
    async def check(client):
        for _ in range(2):
            response = await client.get('/api/local/' + route)
            assert response.status == 200
            assert response.content_type == 'application/pdf'
            assert response.headers['Content-Disposition'].startswith('attachment;')
            assert await response.read() == PDF
        assert harness.pdf_calls == [[1]]
    asyncio.run(exercise(harness, check))
