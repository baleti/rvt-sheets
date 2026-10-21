"""Synthetic tests; no reader, model corpus, or optional PDF parser required."""
import copy
import importlib.util
from pathlib import Path
import re
import shutil
import sys
import zlib
from types import ModuleType, SimpleNamespace

import pytest

from rvtsheets import drawings, pdf


@pytest.fixture
def compose(monkeypatch):
    # This source-only checkout omits compose's rendering/reader dependencies.
    # Load in a private package so the doubles cannot affect other test modules.
    package = "_pdf_drawings_test"
    parent = ModuleType(package)
    parent.__path__ = []
    monkeypatch.setitem(sys.modules, package, parent)
    for name, attrs in {
        "decode": {"FT_MM": 304.8},
        "sheet": {"SheetComposer": None},
        "svg": {"SVG": None},
        "viewdraw": {"ViewDrawer": None},
        "shaded3d": {},
        "viewsvg": {},
        "datums": {"Datums": SimpleNamespace(annotation_rect=lambda *a: None)},
    }.items():
        module = ModuleType(f"{package}.{name}")
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, module.__name__, module)
    spec = importlib.util.spec_from_file_location(
        f"{package}.compose", Path(drawings.__file__).with_name("compose.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def view():
    return {
        "id": 7, "name": "Synthetic", "kind": "drafting", "scale": 50,
        "origin": [10, 20, 0], "right": [1, 0, 0], "up": [0, 1, 0],
        "crop": {"crop_active": True, "origin": [12, 23, 0],
                 "basis": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                 "bounds": [[-1, 3], [-2, 4], [-10, 10]]},
    }


@pytest.mark.parametrize("sizes", [[(25.4, 12.7)], [(25.4, 12.7), (50.8, 25.4)]])
def test_real_svg_pdf(tmp_path, sizes):
    if shutil.which("rsvg-convert") is None:
        pytest.skip("rsvg-convert is not installed")
    inputs = []
    for i, (width, height) in enumerate(sizes):
        path = tmp_path / f"tiny-{i}.svg"
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" '
            f'height="{height}mm"><rect width="1" height="1"/></svg>'
        )
        inputs.append(str(path))
    output = str(tmp_path / "output.pdf")
    assert pdf.svgs_to_pdf(iter(inputs), output) == output
    data = Path(output).read_bytes()
    assert data.startswith(b"%PDF")
    # Recent Cairo compresses page dictionaries in object streams. Expand only
    # those streams; older versions leave the dictionaries in the PDF itself.
    dictionaries = data
    for header, stream in re.findall(
        rb"(<<[^<>]*?/Type\s*/ObjStm\b[^<>]*?>>)\s*stream\r?\n(.*?)\r?\nendstream",
        data, re.S,
    ):
        assert b"/FlateDecode" in header
        dictionaries += b"\n" + zlib.decompress(stream)
    assert len(re.findall(rb"/Type\s*/Page\b", dictionaries)) == len(sizes)
    boxes = re.findall(rb"/MediaBox\s*\[([^]]+)\]", dictionaries)
    assert len(boxes) == len(sizes)
    for box, (width, height) in zip(boxes, sizes):
        assert [float(x) for x in box.split()] == pytest.approx(
            [0, 0, width * 72 / 25.4, height * 72 / 25.4], abs=0.01
        )
    assert not list(tmp_path.glob("*.tmp"))


def test_pdf_missing_converter(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="rsvg-convert not installed"):
        pdf.svgs_to_pdf([], str(tmp_path / "out.pdf"))
    assert not list(tmp_path.iterdir())


def test_scene_cache_keys():
    opts = {"scale": 50, "detail": 2, "filters": False}
    saved = copy.deepcopy(opts)
    key = drawings.scene_name(7, opts)
    assert re.fullmatch(r"scene_7_[0-9a-f]{10}\.json", key)
    assert key == drawings.scene_name(7, dict(reversed(list(opts.items()))))
    assert key == drawings.scene_name(7, dict(opts, cut=None))
    assert key != drawings.scene_name(8, opts)
    assert key != drawings.scene_name(7, dict(opts, scale=100))
    assert opts == saved
    assert drawings.scene_name(7, {}) == drawings.scene_name(7, {"scale": None})
    assert drawings.scene_name(7, {}) != drawings.scene_name(7, {"filters": False})
    assert drawings.scene_name(7, {}) != drawings.scene_name(7, {"cut": 0})
    assert drawings.scene_name(7, {"filters": True}) != drawings.scene_name(7, {"filters": False})


def test_cache_hits_do_not_decode():
    entries = {"view_7.svg": "<svg/>", "sheet_8.svg": "sheet",
               drawings.scene_name(7, {}): '{"prims":[]}',
               "vg_7.json": "compact", "vg_7_full.json": "full"}
    model = object.__new__(drawings.Model)
    model.cache = SimpleNamespace(has=entries.__contains__, read=entries.__getitem__)
    def forbidden():
        pytest.fail("a cache hit must not construct a Decoder")
    model.decoder = forbidden
    assert model.is_cached("view", 7)
    assert not model.is_cached("sheet", 7)
    assert model.svg("view", 7) == "<svg/>"
    assert model.svg("sheet", 8) == "sheet"
    assert drawings.scene_text(model, 7, {}) == '{"prims":[]}'
    assert drawings.vg_text(model, 7) == "compact"
    assert drawings.vg_text(model, 7, full=True) == "full"


def test_crop_rectangles(compose):
    v = view()
    saved = copy.deepcopy(v)
    assert compose.crop_rect_uv(v) == pytest.approx((1, 1, 5, 7))
    assert v == saved
    v["crop"]["basis"] = [[0, 1, 0], [-1, 0, 0], [0, 0, 1]]
    assert compose.crop_rect_uv(v) == pytest.approx((-2, 2, 4, 6))
    v["right"], v["up"] = [0, 1, 0], [-1, 0, 0]
    assert compose.crop_rect_uv(v) == pytest.approx((2, -4, 6, 2))
    v["crop"]["bounds"] = [[3, -1], [4, -2], [0, 0]]
    assert compose.crop_rect_uv(v) == pytest.approx((2, -4, 6, 2))


@pytest.mark.parametrize("crop", [None, {}, {"crop_active": False}, {"crop_active": True}])
def test_disabled_or_incomplete_crop(compose, crop):
    assert compose.crop_rect_uv({"crop": crop}) is None
    assert compose.crop_rect_uv({}) is None


@pytest.mark.parametrize("vp_scale,view_scale,factor", [(0.5, 50, 0.5), (0, 50, 0.02), (None, 0, 0.01)])
def test_viewport_placement(compose, vp_scale, view_scale, factor):
    v = view()
    v["scale"] = view_scale
    doc = {"views": {7: v}}
    drawing = {"extent": (0, 0, 10, 10), "prims": [], "viewports": [
        {"vp": {"view": 7, "scale": vp_scale, "offset": [2, 3, 0]}}
    ]}
    compose.SheetComposer = lambda *a: SimpleNamespace(doc=doc, sty={}, compose=lambda sid: drawing)
    class Canvas:
        def __init__(self, *args):
            self.parts = []
        def P(self, point):
            return (point[0] * 304.8, (10 - point[1]) * 304.8)
        def raw(self, text):
            self.parts.append(text)
        def tostring(self):
            return "".join(self.parts)
    compose.SVG = Canvas
    positions = []
    def body(prims, scale, tx):
        for primitive in prims:
            positions.append(tx(*primitive["origin"]))
        return []
    compose.viewsvg.body = body
    drawer = SimpleNamespace(draw=lambda eid, **kw: {
        "prims": [{"elem": 1, "origin": [4, 5]}] if eid == 7 else [], "stats": {}
    })
    result = compose.sheet_svg(None, 99, doc, drawer, log=lambda *a: None)
    assert positions == [pytest.approx(((2 + 4 * factor) * 304.8, (7 - 5 * factor) * 304.8))]
    match = re.search(r'<clipPath id="vp0"><rect x="([^"]+)" y="([^"]+)" width="([^"]+)" height="([^"]+)"', result)
    assert match is not None
    assert tuple(map(float, match.groups())) == pytest.approx(
        ((2 + factor) * 304.8, (7 - 7 * factor) * 304.8, 4 * factor * 304.8, 6 * factor * 304.8), abs=0.001
    )
    assert 'data-view="7" clip-path="url(#vp0)"' in result


def test_touching_groups_whole_elements_and_includes_boundary(compose):
    prims = [
        {"elem": 1, "pts": [[-2, 0], [-1, 0]]},
        {"elem": 1, "origin": [2, 0]},
        {"elem": 2, "loops": [[[1, 1], [2, 2]]]},
        {"elem": 3, "segs": [[[4, 4], [5, 5]]]},
        {"elem": 4, "text": "no geometry"},
    ]
    assert compose._touching(prims, (0, 0, 1, 1)) == {id(prims[i]) for i in (0, 1, 2, 4)}
    assert compose._touching([], (0, 0, 1, 1)) == set()


def test_datum_ids(compose):
    drawing = {"prims": [{"elem": 1, "layer": "datum"},
                         {"elem": 1, "layer": "datum"},
                         {"elem": 2, "layer": "model"}]}
    assert compose.datum_ids(drawing) == {1}
    assert compose.datum_ids(drawing) is drawing["_datums"]
    assert compose.datum_ids({"prims": []}) == set()
