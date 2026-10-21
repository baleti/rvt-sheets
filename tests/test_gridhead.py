import numpy as np
from rvtsheets.gridhead import order_ends

S = np.array([-50.0, -43.6]); N = np.array([-50.0, 56.3])   # south / north end of a vertical line


def t(uv0, uv1, **kw):
    a = dict(cls='Grid', view_kind='plan', grid_ext=False, has_extent=False, on_x=False, xvec_z=1.0)
    a.update(kw)
    o0, o1 = order_ends(uv0, uv1, **a)
    assert o0.dtype == float and o1.dtype == float
    return o0, o1


def test_snowdon_vertical_head_north():
    o0, o1 = t(S, N, xvec_z=1.0)
    assert np.allclose(o0, N) and np.allclose(o1, S)


def test_facades_vertical_head_stays_south():
    o0, o1 = t(S, N, xvec_z=-1.0)
    assert np.allclose(o0, S) and np.allclose(o1, N)
    o0, o1 = t(S, N, xvec_z=-1.0, xflip=False)
    assert np.allclose(o0, N)


def test_already_north_unchanged():
    o0, o1 = t(N, S, xvec_z=1.0)
    assert np.allclose(o0, N)


def test_on_x_keeps_low_end_unless_gridnorth():
    o0, _ = t(S, N, on_x=True)
    assert np.allclose(o0, S)
    o0, _ = t(S, N, on_x=True, gridnorth=True)
    assert np.allclose(o0, N)


def test_horizontal_lines_unchanged():
    a = np.array([-100.0, 3.0]); b = np.array([80.0, 3.5])
    o0, o1 = t(a, b)
    assert np.allclose(o0, a) and np.allclose(o1, b)


def test_extent_record_or_grid_ext_blocks_rule3():
    o0, _ = t(S, N, has_extent=True)
    assert np.allclose(o0, S)
    o0, _ = t(S, N, grid_ext=True)
    assert np.allclose(o0, S)


def test_section_grid_top_end():
    o0, o1 = t(S, N, view_kind='section')
    assert np.allclose(o0, N) and np.allclose(o1, S)
    o0, _ = t(S, N, view_kind='section', grid_ext=True)
    assert np.allclose(o0, S)


def test_level_never_swapped_and_inputs_not_mutated():
    s, n = S.copy(), N.copy()
    o0, o1 = t(s, n, cls='Level')
    assert np.allclose(o0, S)
    t(s, n, view_kind='section')
    assert np.allclose(s, S) and np.allclose(n, N)
