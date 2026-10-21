import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from rvtsheets.vg import display as D


@pytest.mark.parametrize('inp,exp', [(1, 'wireframe'), (2, 'hidden'), (3, 'shaded'), (4, 'shaded_edges'), (5, 'realistic'), (6, 'raytrace'), (7, 'consistent'), (8, 'rendering'), ('7', 'consistent'), (None, 'hidden'), (99, 'hidden'), ('x', 'hidden'), (2.0, 'hidden')])
def test_display_style(inp, exp):
    assert D.display_style(inp) == exp


def test_keys():
    r = D.drawing_rules('hidden', 'plan')
    assert set(r) == {'occlude', 'cut_caps', 'surface_fills', 'shaded_faces'} and all(isinstance(x, bool) for x in r.values())


@pytest.mark.parametrize('kind', ['plan', 'section', 'elevation', 'weird'])
def test_wireframe_2d(kind):
    r = D.drawing_rules('wireframe', kind, 1)
    assert r == {'occlude': False, 'cut_caps': False, 'surface_fills': False, 'shaded_faces': False}
    assert D.drawing_rules('wireframe', kind)['occlude'] is False


@pytest.mark.parametrize('kind', ['plan', 'section', 'elevation'])
def test_wireframe_structural_stays_hlr(kind):
    r = D.drawing_rules('wireframe', kind, 2)
    assert r['occlude'] is True and r['cut_caps'] is True and r['surface_fills'] is False


def test_wireframe_3d():
    assert D.drawing_rules('wireframe', '3d', 2)['occlude'] is False
    assert D.drawing_rules('wireframe', '3d')['cut_caps'] is False


@pytest.mark.parametrize('style', ['hidden', 'shaded', 'shaded_edges', 'realistic', 'raytrace', 'consistent', 'rendering', 'nonsense'])
def test_solid_styles(style):
    for kind in ('plan', '3d'):
        r = D.drawing_rules(style, kind)
        assert r['occlude'] and r['cut_caps'] and r['surface_fills']
    assert D.drawing_rules(style, 'plan')['shaded_faces'] is False
    assert D.drawing_rules(style, '3d')['shaded_faces'] is (style in ('shaded', 'shaded_edges', 'realistic', 'raytrace', 'consistent', 'rendering'))
