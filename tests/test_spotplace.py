import math, itertools
import numpy as np
from rvtsheets.spotplace import place


def ref(a, off, Mv, ang, dirx, scale, neg_enabled=True):
    sc = scale if scale else 1
    ca, sa = math.cos(ang), math.sin(ang)
    rot = abs(ang) > 0.5
    neg = off[1] < 0 and rot and neg_enabled
    endh = off[1] < 0 and not rot and dirx < -0.5 and neg_enabled
    o0 = -off[0] if neg else off[0]
    b = np.asarray(a, float) + (Mv @ np.array([-(ca * o0 - sa * off[1]), sa * o0 + ca * off[1], off[2]]))[:2]
    if neg: b = b + np.array([1.0, 0.0]) * (0.0115 * sc) + np.array([ca, sa]) * (-0.0034 * sc)
    elif rot: b = b + np.array([-0.003, -0.0085]) * sc
    elif endh: b = b + np.array([ca, sa]) * (0.0197 * sc)
    else: b = b + np.array([ca, sa]) * (0.0115 * sc)
    return b, (0 if ((abs(ang) < 0.5 and not endh) or neg) else 2)


def test_grid_matches_reference():
    Mvs = [np.eye(3), np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1.0]]), np.diag([1, -1, 1.0])]
    for Mv, ang, dirx, oy, sc, ne in itertools.product(Mvs, (0.0, math.pi / 2, -1.4399, 0.35), (1.0, -1.0, 0.1), (-0.8, 1.92, 0.0), (48, 96, None, 0), (True, False)):
        off = np.array([1.37, oy, 0.0]); a = np.array([3.0, -2.0])
        b, h = place(a, off, Mv, ang, dirx, sc, ne)
        rb, rh = ref(a, off, Mv, ang, dirx, sc, ne)
        assert np.allclose(b, rb, atol=1e-12) and h == rh and isinstance(b, np.ndarray) and b.shape == (2,)


def test_pinned():
    b, h = place(np.zeros(2), np.array([1.0, -0.8, 0.0]), np.eye(3), math.pi / 2, 1.0, 96)
    r_, rh_ = ref(np.zeros(2), np.array([1.0, -0.8, 0.0]), np.eye(3), math.pi / 2, 1.0, 96)
    assert h == 0 and rh_ == 0 and np.allclose(b, r_)
    b, h = place(np.zeros(2), np.array([1.0, 1.92, 0.0]), np.eye(3), 0.0, 1.0, 96)
    assert h == 0 and np.allclose(b, [-1.0 + 0.0115 * 96, 1.92])
    b, h = place(np.zeros(2), np.array([1.0, -0.8, 0.0]), np.eye(3), 0.0, -1.0, 96)
    assert h == 2 and np.allclose(b, [-1.0 + 0.0197 * 96, -0.8])
