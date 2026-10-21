"""Additional renderer contracts; missing decoder/text helpers are explicit doubles.

These tests exercise viewsvg's choices and helper arguments, not the absent
svg.py's typography or escaping implementation. No real package is patched.
"""
import html
import importlib
import math
from pathlib import Path
import sys
import types
import xml.etree.ElementTree as ET
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def _no_dedupe(monkeypatch):
    monkeypatch.setenv('RVT_DEDUPE', '0')      # these tests feed repeated identical prims on purpose (tests/test_dedupe.py covers the de-duplication)


@pytest.fixture
def renderer(monkeypatch):
    name = '_viewsvg_more'
    package = types.ModuleType(name)
    package.__path__ = [str(Path(__file__).resolve().parents[1] / 'rvtsheets')]
    decode = types.ModuleType(name + '.decode')
    decode.FT_MM = 304.8
    decode.color = lambda c: [c & 255, (c >> 8) & 255, (c >> 16) & 255]
    helper = types.ModuleType(name + '.svg')
    helper.font_stack = lambda font: font or 'Test Font'
    helper.EM = 1.0
    helper.LINE_PITCH = 1.25
    helper.line_pitch = Mock(return_value=1.25)
    helper.revit_pt = lambda size: size
    helper.first_baseline = Mock(return_value=7.0)
    helper.rtf_first = Mock(return_value=3.0)
    helper.box_slack = Mock(return_value=0.25)

    def spans(lines, dx, first, pitch):
        return ''.join(
            f'<tspan x="{dx}" dy="{first if i == 0 else pitch}">'
            f'{html.escape(line)}</tspan>' for i, line in enumerate(lines)
        )

    helper.tspans = Mock(side_effect=spans)
    for module in (package, decode, helper):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setenv('RVT_DOTS', '0')
    module = importlib.import_module(name + '.viewsvg')
    try:
        yield module, helper
    finally:
        sys.modules.pop(name + '.viewsvg', None)


def line(**changes):
    return dict(t='line', pts=[[0, 0], [10, 10]], layer='projection',
                elem='model', style=dict(w=0.2, rgb=[128, 128, 128], dash=[2.5, 0.75])) | changes


def body(renderer, prims, scale=100, **options):
    return ET.fromstring('<svg>' + ''.join(renderer[0].body(
        prims, scale, lambda x, y: (x * 304.8 / scale, -y * 304.8 / scale),
        **options)) + '</svg>')


def view(renderer, prims, **options):
    return ET.fromstring(renderer[0].view_svg({'prims': prims}, scale=304.8, **options))


@pytest.mark.parametrize('scale', [1, 50, 1000])
@pytest.mark.parametrize('kind', ['line', 'segs', 'cut'])
def test_paper_dash_and_precomputed_halftone_survive_scale(renderer, scale, kind):
    # Styles arrive with their halftone RGB already resolved; viewsvg has no
    # halftone flag. Dash lengths and line weights are already paper mm too.
    prim = line(t=kind, segs=[[[0, 0], [10, 10]]], loops=[], fill=None)
    node, = body(renderer, [prim], scale)
    assert [float(x) for x in node.get('stroke-dasharray').split(',')] == [2.5, 0.75]
    assert float(node.get('stroke-width')) == 0.2
    assert node.get('stroke') == '#808080'
    assert node.get('d').endswith(f'L{3048 / scale:.3f} {-3048 / scale:.3f}')


@pytest.mark.parametrize('halign,anchor', [(0, 'start'), (1, 'middle'), (2, 'end'), (99, 'start')])
@pytest.mark.parametrize('valign', [0, 1, 2])
def test_anchor_alignment_forwards_vertical_layout(renderer, halign, anchor, valign):
    p = dict(t='text', text='A\nB\nC', origin=[2, 3], size=1,
             anchor=True, halign=halign, valign=valign, box=[100, 100], font='Example')
    node, = body(renderer, [p], scale=304.8)
    assert node.get('text-anchor') == anchor
    assert node.get('transform') == 'translate(2.000 -3.000) rotate(0.000)'
    assert [n.text for n in node] == ['A', 'B', 'C']
    renderer[1].first_baseline.assert_called_once_with(valign, 3, 1.25, 1.0, 'Example', 0.25)
    renderer[1].tspans.assert_called_once_with(['A', 'B', 'C'], 0.0, 7.0, 1.25)
    renderer[1].rtf_first.assert_not_called()


@pytest.mark.parametrize('direction,angle', [([1, 1], -45), ([-1, 0], -180), ([0, -1], 90)])
@pytest.mark.parametrize('halign,dx', [(0, 0), (1, 4), (2, 8)])
def test_rtf_overrides_anchor_and_aligns_inside_box(renderer, direction, angle, halign, dx):
    node, = body(renderer, [dict(t='text', text='label', origin=[0, 0],
                               x=direction, size=1, box=[8, 2], anchor=True,
                               rtf='', halign=halign)], scale=304.8)
    assert node.get('transform') == f'translate(0.000 0.000) rotate({angle:.3f})'
    assert float(node[0].get('x')) == dx
    assert float(node[0].get('dy')) == 3
    renderer[1].first_baseline.assert_not_called()
    renderer[1].rtf_first.assert_called_once_with(1.0, None)


def test_special_text_and_blank_lines_reach_span_helper_unchanged(renderer):
    lines = ['& < > "', '', 'tail', '']
    node, = body(renderer, [dict(t='text', text='\n'.join(lines), origin=[0, 0],
                               font='A&B <Font>')])
    assert node.get('font-family') == 'A&B <Font>'
    assert [n.text or '' for n in node] == lines
    assert renderer[1].tspans.call_args.args[0] == lines
    assert node.get('{http://www.w3.org/XML/1998/namespace}space') == 'preserve'


def test_pattern_is_explicit_hatch_geometry_above_solid_fill(renderer):
    # The renderer's pattern representation is segs, not an SVG pattern field.
    fill = dict(t='fill', layer='cut_fill', elem='solid', color=0x332211,
                loops=[[[0, 0], [4, 0], [4, 4], [0, 4]]])
    hatch = line(t='segs', layer='cut_fill', elem='hatch',
                 segs=[[[0, 1], [4, 1]], [[0, 3], [4, 3]]])
    root = body(renderer, [line(elem='edge', layer='cut'), fill, hatch], scale=304.8)
    assert [n.get('data-e') for n in root] == ['solid', 'hatch', 'edge']
    assert root[0].get('fill') == '#112233'
    assert root[0].get('fill-rule') == 'evenodd'
    assert root[1].get('fill') == 'none'
    assert root[1].get('d') == 'M0.000 -1.000 L4.000 -1.000 M0.000 -3.000 L4.000 -3.000'
    assert root.find('pattern') is None


def test_crop_resolves_image_and_path_references_and_paint_order(renderer):
    image = dict(t='image', center=[5, 5], w=4, h=2,
                 uri='data:image/png;base64,AA==', layer='underlay', elem='image')
    annotation = line(layer='annotation', elem='note')
    root = view(renderer, [annotation, line(), image], crop=(2, 2, 8, 8), hang=False)
    clip = root.find('./{*}defs/{*}clipPath')
    assert clip is not None
    assert len(clip.findall('{*}rect')) == 1
    painted = [n for n in root if n.get('data-e')]
    assert [n.get('data-e') for n in painted] == ['image', 'model', 'note']
    assert [n.get('clip-path') for n in painted] == [f'url(#{clip.get("id")})'] * 2 + [None]
    assert painted[0].tag == '{http://www.w3.org/2000/svg}image'
    assert float(painted[0].get('width')) == 4
    assert float(painted[0].get('height')) == 2
    assert view(renderer, [line()]).find('.//{*}clipPath') is None


def test_empty_body_and_input_are_unchanged(renderer):
    prims = []
    assert len(body(renderer, prims)) == 0
    root = view(renderer, prims)
    assert root.tag == '{http://www.w3.org/2000/svg}svg'
    assert float(root.get('width').removesuffix('mm')) > 0
    assert prims == []


@pytest.mark.parametrize('offset', [1e12, -1e12])
def test_huge_world_offset_preserves_local_geometry(renderer, offset):
    root = view(renderer, [line(pts=[[offset, offset], [offset + 10, offset + 20]])], margin_mm=2)
    assert list(map(float, root.get('viewBox').split())) == [0, 0, 14, 24]
    assert root.find('{*}path').get('d') == 'M2.000 22.000 L12.000 2.000'


def test_huge_extent_stays_finite(renderer):
    root = view(renderer, [line(pts=[[-1e12, -1e12], [1e12, 1e12]])])
    dimensions = list(map(float, root.get('viewBox').split()))
    assert all(math.isfinite(x) for x in dimensions)
    assert dimensions[2:] == [2e12 + 10, 2e12 + 10]


@pytest.mark.xfail(strict=True, raises=ET.ParseError,
                   reason='image URI is interpolated without XML attribute escaping')
def test_image_uri_query_string_is_xml_safe(renderer):
    uri = 'https://example.invalid/image.png?a=1&b=2'
    node, = body(renderer, [dict(t='image', center=[0, 0], w=1, h=1, uri=uri)])
    assert node.get('href') == uri
