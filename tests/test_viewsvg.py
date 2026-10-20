"""Characterise view SVG output using in-memory drawing primitives."""
import importlib
import os
import sys
import types
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def svg(monkeypatch):
    # This source-only checkout omits decode.py. Load the real SVG modules in
    # an isolated package with just their two decoder dependencies supplied.
    # Nothing is injected into the real rvtsheets package or other tests.
    name = '_viewsvg_characterisation'
    package = types.ModuleType(name)
    package.__path__ = [os.path.join(os.path.dirname(os.path.dirname(__file__)), 'rvtsheets')]
    decode = types.ModuleType(name + '.decode')
    decode.FT_MM = 304.8
    decode.color = lambda c: [c & 255, (c >> 8) & 255, (c >> 16) & 255]
    monkeypatch.setitem(sys.modules, name, package)
    monkeypatch.setitem(sys.modules, name + '.decode', decode)
    for key in ('RVT_DOTS', 'RVT_PTSNAP', 'RVT_TEXTBASE', 'RVT_BOXSLACK'):
        monkeypatch.setenv(key, '1')
    monkeypatch.setenv('RVT_ARIAL_NARROW', 'arial')
    try:
        yield importlib.import_module(name + '.viewsvg')
    finally:
        sys.modules.pop(name + '.viewsvg', None)
        sys.modules.pop(name + '.svg', None)


def line(**changes):
    return dict(t='line', pts=[[0, 0], [2, 1]],
                style={'w': 0.18, 'rgb': [0, 0, 0], 'dash': None},
                layer='projection', elem=5) | changes


def elements(svg, prims, **kwargs):
    return [ET.fromstring(s) for s in svg.body(prims, 100, lambda x, y: (2 * x + 1, 3 - 2 * y), **kwargs)]


def view(svg, prims, **kwargs):
    return ET.fromstring(svg.view_svg({'prims': prims}, **kwargs))


def dimensions(root):
    return tuple(map(float, root.get('viewBox').split()[2:]))


@pytest.mark.parametrize(('value', 'expected'), [
    (None, '#000000'), ([], '#000000'), ([255, 16, 0], '#ff1000'),
    ([1.9, 2.1, 3.8, 99], '#010203'),
])
def test_rgb(svg, value, expected):
    assert svg._rgb(value) == expected


@pytest.mark.parametrize('layer', sorted(['cut', 'projection', 'underlay', 'symbolic', 'symbolic_fill', 'cut_fill', 'surface_fill']))
def test_bounds_model_layers_exclude_annotations(svg, layer):
    lo, hi = svg.bounds([line(layer=layer), line(layer='annotation', pts=[[-9, -8], [10, 11]], hang=True)])
    assert lo.tolist() == [0, 0]
    assert hi.tolist() == [2, 1]


@pytest.mark.parametrize('model_only', [True, False])
def test_bounds_fallback_and_all_geometry_fields(svg, model_only):
    lo, hi = svg.bounds([{'layer': 'annotation', 'pts': [[1, 2, 99]],
                         'loops': [[[-3, 4, 0]]], 'segs': [[[5, -6, 0]]]}], model_only)
    assert lo.tolist() == [-3, -6]
    assert hi.tolist() == [5, 4]


def test_bounds_explicit_all_and_no_point_geometry(svg):
    lo, hi = svg.bounds([line(), line(layer='text', pts=[[-5, -6], [8, 9]])], False)
    assert lo.tolist() == [-5, -6]
    assert hi.tolist() == [8, 9]
    assert svg.bounds([]) is None
    assert svg.bounds([{'t': 'text', 'origin': [10, 20]}]) is None


@pytest.mark.parametrize(('prim', 'expected'), [
    ({'pts': [[-1, 0.5], [2, 0.5]]}, True),
    ({'pts': [[1, 1], [2, 2]]}, True),
    ({'pts': [[1.01, 0], [2, 1]]}, False),
    ({'loops': [[[0, 0], [1, 1]]]}, True),
    ({'segs': [[[3, 3], [4, 4]]]}, False),
    ({'origin': [-1, -1, 100]}, False), ({}, True),
    ({'pts': [[3, 3]], 'loops': [[[0, 0]]], 'origin': [0, 0]}, False),
    # Only bounding boxes are tested, not actual segment intersection.
    ({'pts': [[-2, 0.1], [0.1, 2]]}, True),
])
def test_inside(svg, prim, expected):
    assert bool(svg._inside(prim, ((0, 0), (1, 1)))) is expected


@pytest.mark.parametrize(('width', 'expected'), [(0, '0.050'), (-1, '0.050'), (0.18, '0.180')])
def test_line_stroke_and_transform(svg, width, expected):
    node, = elements(svg, [line(pts=[[0, 0, 8], [1, 1, 9]], style={'w': width, 'rgb': [1, 2, 255], 'dash': [1, 0.125]})])
    assert node.tag == 'path'
    assert node.attrib == {'d': 'M1.000 3.000 L3.000 1.000', 'fill': 'none',
                           'stroke': '#0102ff', 'stroke-width': expected,
                           'stroke-dasharray': '1.00,0.12', 'stroke-linecap': 'round',
                           'stroke-linejoin': 'round', 'data-e': '5'}


def test_segs_disconnected_and_missing_element(svg):
    p = line(t='segs', segs=[[[0, 0], [1, 0]], [[2, 1], [3, 1]]])
    p.pop('elem')
    node, = elements(svg, [p])
    assert node.get('d') == 'M1.000 3.000 L3.000 3.000 M5.000 1.000 L7.000 1.000'
    assert node.get('data-e') == 'None'
    assert 'stroke-dasharray' not in node.attrib


@pytest.mark.parametrize(('color', 'expected'), [([1, 2, 3], '#010203'), (None, '#888'), ([], '#888'), ([0, 0, 0], '#000000')])
def test_fill_evenodd(svg, color, expected):
    node, = elements(svg, [{'t': 'fill', 'loops': [[[0, 0], [1, 0]], [[2, 1], [3, 1]]], 'color': color, 'elem': 7}])
    assert node.attrib == {'d': 'M1.000 3.000 L3.000 3.000 Z M5.000 1.000 L7.000 1.000 Z',
                           'fill': expected, 'fill-rule': 'evenodd', 'stroke': 'none', 'data-e': '7'}


def test_cut_only_closed_loops_filled_then_stroked(svg):
    nodes = elements(svg, [line(t='cut', loops=[[[0, 0], [1, 0], [1, 1], [0, 0]], [[5, 5], [6, 6]]],
                               segs=[[[0, 0], [1, 0]]], fill=[255, 0, 0])])
    assert len(nodes) == 2
    assert nodes[0].get('fill-rule') == 'evenodd'
    assert nodes[0].get('fill') == '#ff0000'
    assert nodes[0].get('d') == 'M1.000 3.000 L3.000 3.000 L3.000 1.000 L1.000 3.000 Z'
    assert nodes[1].get('d') == 'M1.000 3.000 L3.000 3.000'


def test_layer_order_and_stability(svg):
    order = ['mask', 'underlay', 'room_fill', 'symbolic_fill', 'cut_fill', 'surface_fill', 'projection', 'cut', 'symbolic', 'annotation_fill', 'unknown', 'text']
    prims = [line(layer=k, elem=k) for k in reversed(order[:-2])]
    prims += [line(layer=k, elem=k) for k in order[-2:]]
    assert [n.get('data-e') for n in elements(svg, prims)] == order
    assert [n.get('data-e') for n in elements(svg, [line(elem=2), line(elem=1)])] == ['2', '1']


def test_detail_order_precedes_layer_and_custom_order(svg):
    prims = [line(layer='mask', order=2, elem=4), line(layer='projection', order=1, elem=3),
             line(layer='mask', order=1, elem=2), line(layer='cut', elem=1)]
    assert [n.get('data-e') for n in elements(svg, prims)] == ['1', '2', '3', '4']
    assert [n.get('data-e') for n in elements(svg, [line(layer='cut', elem=1), line(elem=2)], layer_order=('cut', 'projection'))] == ['1', '2']


@pytest.mark.parametrize('layer', ['mask', 'underlay', 'projection', 'cut', 'symbolic', 'symbolic_fill', 'cut_fill', 'surface_fill', 'room_fill', 'annotation_fill', 'annotation', 'text'])
def test_model_clip_attribute(svg, layer):
    node, = elements(svg, [line(layer=layer)], mclip=True)
    expected = layer in {'mask', 'underlay', 'projection', 'cut', 'symbolic', 'symbolic_fill', 'cut_fill', 'surface_fill'}
    assert node.get('clip-path') == ('url(#cropclip)' if expected else None)
    assert 'clip-path' not in elements(svg, [line(layer=layer)])[0].attrib


def test_clip_filters_all_layers_but_keeps_crossing_lines(svg):
    nodes = elements(svg, [line(pts=[[-2, 0], [2, 0]]), line(layer='annotation', pts=[[5, 5], [6, 6]])], clip=((-1, -1), (1, 1)))
    assert len(nodes) == 1
    assert nodes[0].get('d') == 'M-3.000 3.000 L5.000 3.000'
    assert 'clip-path' not in nodes[0].attrib


def test_image_geometry(svg):
    node, = elements(svg, [{'t': 'image', 'center': [2, 3], 'w': 4, 'h': 2, 'uri': 'data:image/png;base64,AA==', 'elem': 9, 'layer': 'underlay'}], mclip=True)
    assert node.tag == 'image'
    assert node.attrib == {'x': '1.000', 'y': '-5.000', 'width': '8.000', 'height': '4.000',
                           'href': 'data:image/png;base64,AA==', 'preserveAspectRatio': 'none', 'data-e': '9', 'clip-path': 'url(#cropclip)'}


def test_text_escaping_font_alignment_and_transform(svg):
    p = {'t': 'text', 'text': '<A>&\n\nB', 'origin': [1, 2], 'size': 0.1, 'font': 'Arial Narrow',
         'x': [0, 1], 'halign': 2, 'box': [2, 1], 'bold': True, 'width_scale': 0.8,
         'color': 0x030201, 'elem': 6, 'layer': 'projection'}
    node, = elements(svg, [p], mclip=True)
    assert node.tag == 'text'
    assert node.get('transform') == 'translate(3.000 -1.000) rotate(-90.000) scale(0.8000 1)'
    assert node.get('font-family') == "Arial, 'Liberation Sans', Arimo, Helvetica, sans-serif"
    assert node.get('font-size') == '0.529'  # 1.2 pt rounds up to 1.5 pt.
    assert node.get('text-anchor') == 'end'
    assert node.get('font-weight') == 'bold'
    assert node.get('fill') == '#010203'
    assert node.get('data-e') == '6'
    assert node.get('{http://www.w3.org/XML/1998/namespace}space') == 'preserve'
    assert 'clip-path' not in node.attrib  # text_svg does not receive body's attributes.
    assert [n.text for n in node] == ['<A>&', 'B']
    assert [n.attrib for n in node] == [{'x': '6.096', 'dy': '0.476'}, {'x': '6.096', 'dy': '1.291'}]


@pytest.mark.parametrize('prim', [{'t': 'text', 'text': '', 'origin': [0, 0]}, {'t': 'text', 'text': 'A'}, {'t': 'image', 'uri': ''}, {'t': 'unknown'}])
def test_unsupported_or_incomplete_primitives_are_omitted(svg, prim):
    assert elements(svg, [prim]) == []


@pytest.mark.parametrize(('scale', 'margin', 'size'), [(100, 5, (16.096, 13.048)), (50, 2, (16.192, 10.096))])
def test_view_scale_margin_and_y_flip(svg, scale, margin, size):
    root = view(svg, [line()], scale=scale, margin_mm=margin)
    assert root.tag == '{http://www.w3.org/2000/svg}svg'
    assert dimensions(root) == pytest.approx(size)
    assert root.get('width') == f'{size[0]:.1f}mm'
    assert root.get('height') == f'{size[1]:.1f}mm'
    assert root[0].attrib == {'width': '100%', 'height': '100%', 'fill': '#fff'}
    assert root[1].get('d') == f'M{margin:.3f} {size[1] - margin:.3f} L{size[0] - margin:.3f} {margin:.3f}'


def test_crop_definition_and_model_clip(svg):
    root = view(svg, [line(pts=[[0, 0], [10, 10]])], scale=304.8, margin_mm=2, crop=(2, 3, 8, 9))
    assert dimensions(root) == (10, 10)
    clip = root.find('.//{*}clipPath')
    assert clip.get('id') == 'cropclip'
    assert clip[0].attrib == {'x': '2.000', 'y': '2.000', 'width': '6.000', 'height': '6.000'}
    assert root[-1].get('clip-path') == 'url(#cropclip)'


@pytest.mark.parametrize('crop', [None, (0, 0, 2, 1)])
def test_underlay_bytes_geometry_and_order(svg, crop):
    root = view(svg, [line()], scale=304.8, margin_mm=1, crop=crop,
                under=(b'\x89PNG\r\n\x1a\n', (0, 0, 2, 1)))
    group = root.find('{*}g')
    assert group.get('clip-path') == ('url(#cropclip)' if crop else None)
    assert group[0].attrib == {'x': '1.000', 'y': '1.000', 'width': '2.000', 'height': '1.000',
                               'href': 'data:image/png;base64,iVBORw0KGgo=', 'preserveAspectRatio': 'none'}
    assert list(root).index(group) < list(root).index(root.find('{*}path'))


@pytest.mark.parametrize('hang', [True, False])
@pytest.mark.parametrize('explicit', [True, False])
def test_hanging_annotation_extents(svg, hang, explicit):
    annotation = line(layer='datum' if explicit else 'annotation', pts=[[3, 0], [4, 1]], hang=explicit)
    root = view(svg, [line(), annotation], scale=304.8, margin_mm=0, hang=hang)
    assert dimensions(root) == (4 if hang else 2, 1)


def test_crop_hanging_geometry_expands_even_when_hang_false(svg):
    root = view(svg, [line(pts=[[0, 0], [10, 10]]), line(layer='datum', pts=[[-100, 4], [3, 5]])],
                scale=304.8, margin_mm=0, crop=(2, 2, 8, 8), hang=False)
    assert dimensions(root) == (76, 6)  # Left head limited to crop left minus 70 mm.


@pytest.mark.parametrize('prims', [[], [{'t': 'text', 'text': 'A', 'origin': [0, 0]}]])
def test_empty_view_ignores_crop_underlay_and_margin(svg, prims):
    root = view(svg, prims, scale=100, margin_mm=99, crop=(0, 0, 1, 1), under=(b'png', (0, 0, 1, 1)))
    assert root.attrib == {'width': '10mm', 'height': '10mm'}
    assert len(root) == 0


@pytest.mark.parametrize('enabled', ['0', '1'])
def test_stipple_short_segments_become_midpoint_dots(svg, monkeypatch, enabled):
    monkeypatch.setenv('RVT_DOTS', enabled)
    prim = line(t='segs', layer='cut_fill',
                segs=[[[0, 0], [0.1, 0]]] * 9 + [[[0, 0], [1, 0]]],
                style={'w': 0.1, 'rgb': [0, 0, 0], 'dash': None})
    nodes = elements(svg, [prim])
    if enabled == '1':
        assert len(nodes) == 2
        assert nodes[0].get('stroke-width') == '0.340'
        assert nodes[0].get('d') == ' '.join(['M1.100 3.000 L1.100 3.000'] * 9)
        assert nodes[1].get('d') == 'M1.000 3.000 L3.000 3.000'
    else:
        assert len(nodes) == 1
        assert nodes[0].get('d').count('M') == 10
    assert nodes[-1].get('stroke-width') == '0.100'


@pytest.mark.parametrize(('valign', 'dy'), [(0, '0.476'), (1, '-0.144'), (2, '-0.765')])
def test_anchored_multiline_text_baseline(svg, valign, dy):
    node, = elements(svg, [{'t': 'text', 'text': 'A\nB', 'origin': [0, 0],
                           'size': 0.1, 'anchor': True, 'valign': valign}])
    assert node.get('text-anchor') == 'start'
    assert node[0].attrib == {'x': '0.000', 'dy': dy}
    assert node[1].attrib == {'x': '0.000', 'dy': '0.646'}


def test_hanging_text_estimated_width_and_multiline_height(svg):
    prim = {'t': 'text', 'text': 'AB\nC', 'origin': [3, 0], 'size': 0.72,
            'layer': 'text', 'elem': 10}
    root = view(svg, [line(), prim], scale=304.8, margin_mm=0)
    # Longest line: 2 * 0.55 * size / 0.72; one newline: size * 1.2.
    assert dimensions(root) == (4.1, 1.864)


def test_disjoint_crop_keeps_model_extents_but_defines_clip(svg):
    root = view(svg, [line()], scale=304.8, margin_mm=0, crop=(5, 5, 6, 6))
    assert dimensions(root) == (2, 1)
    assert root.find('.//{*}clipPath/{*}rect').attrib == {
        'x': '5.000', 'y': '-5.000', 'width': '1.000', 'height': '1.000',
    }
