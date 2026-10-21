"""viewdraw.ViewDrawer._shade_plan on synthetic prims (no corpus): shaded (3) and consistent colours (7) plan display"""
import collections, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.viewdraw import ViewDrawer


def _vd():
    vd = ViewDrawer.__new__(ViewDrawer)
    vd.stats = collections.Counter()
    vd.materials = lambda: {25: {'color': [128, 128, 128]}, 1253: {'color': [127, 127, 127]}}
    return vd


def _floor():
    T = np.array([[[0, 0, 0], [10, 0, 0], [10, 10, 0]], [[0, 0, 0], [10, 10, 0], [0, 10, 0]]], float)
    return (7, -2000032, T, T, None, None, {'_mat': 1253})


PRIMS = [{'t': 'segs', 'layer': 'projection', 'elem': 7, 'segs': []},
         {'t': 'cut', 'elem': 5, 'loops': [[[0, 0], [1, 0], [1, 1], [0, 0]]], 'layer': 'cut', 'segs': []},
         {'t': 'line', 'layer': 'symbolic', 'elem': 9, 'pts': [[0, 0], [1, 1]]}]
CLIPPED = [_floor(), (5, -2000011, np.zeros((1, 3, 3)), None, None, None, {'_mat': 25})]


def _view(surf, disc=None):
    return {'kind': 'plan', 'discipline': disc, 'display': {'m_model': {'m_surfaces': surf}}}


def test_other_styles_untouched():
    for s in (1, 2, 4, None):
        assert _vd()._shade_plan(list(PRIMS), CLIPPED, _view(s)) == PRIMS


def test_structural_untouched():
    assert _vd()._shade_plan(list(PRIMS), CLIPPED, _view(3, 2)) == PRIMS


def test_shaded_drops_edges_and_fills():
    vd = _vd(); out = vd._shade_plan(list(PRIMS), CLIPPED, _view(3))
    assert not any(p.get('layer') == 'projection' for p in out)
    assert not any(p.get('t') == 'cut' for p in out)
    assert any(p.get('t') == 'line' and p['layer'] == 'symbolic' for p in out)      # symbols stay
    fills = [p for p in out if p['t'] == 'fill']
    assert out[0]['t'] == 'fill' and out[0]['layer'] == 'surface_fill' and out[0]['color'] == [133, 133, 133]       # 127 lit by 134/128
    cut = [p for p in fills if p['layer'] == 'cut_fill'][0]
    assert cut['color'] == [134, 134, 134] and cut['elem'] == 5
    assert vd.stats['shaded_plan'] == 1 and vd.stats['shaded_edges_dropped'] == 1


def test_consistent_keeps_edges_unlit():
    vd = _vd(); out = vd._shade_plan(list(PRIMS), CLIPPED, _view(7))
    assert [p for p in out if p['t'] != 'fill'] == PRIMS
    cols = sorted(tuple(p['color']) for p in out if p['t'] == 'fill')
    assert cols == [(127, 127, 127), (128, 128, 128)]
    assert vd.stats['consistent_plan'] == 1


def test_default_grey_without_material():
    vd = _vd(); vd.materials = lambda: {}
    out = vd._shade_plan(list(PRIMS), [_floor()[:6] + ({},)], _view(3))
    assert out[0]['color'] == [134, 134, 134]
