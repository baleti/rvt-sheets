"""ViewDrawer._carve_tris: every hosted opening is cut out of a wall face, not only the first one"""
import numpy as np
import pytest
from rvtsheets.viewdraw import ViewDrawer


def quad(z=-1.0):
    a = [[0, 0, z], [10, 0, z], [10, 5, z], [0, 5, z]]
    return np.array([[a[0], a[1], a[2]], [a[0], a[2], a[3]]], float)


def covered(T, p):
    for t in T:
        a, b, c = t[:, :2]
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12: continue
        l1 = ((b[1] - c[1]) * (p[0] - c[0]) + (c[0] - b[0]) * (p[1] - c[1])) / d
        l2 = ((c[1] - a[1]) * (p[0] - c[0]) + (a[0] - c[0]) * (p[1] - c[1])) / d
        if l1 >= 0 and l2 >= 0 and l1 + l2 <= 1: return True
    return False


BOXES = [(np.array([1.0, 1.0, -2.0]), np.array([3.0, 4.0, 0.0])), (np.array([6.0, 1.0, -2.0]), np.array([8.0, 4.0, 0.0]))]


def carve(T, monkeypatch, seq):
    monkeypatch.setenv('RVT_CARVE_SEQ', seq)
    return ViewDrawer._carve_tris(None, T, BOXES)


def test_both_openings_are_cut(monkeypatch):
    T = carve(quad(), monkeypatch, '1')
    assert not covered(T, (2, 2)) and not covered(T, (7, 2))
    assert covered(T, (5, 2)) and covered(T, (0.5, 0.5)) and covered(T, (9, 4.5))


def test_old_behaviour_keeps_the_second_opening_filled(monkeypatch):
    T = carve(quad(), monkeypatch, '0')
    assert not covered(T, (2, 2)) and covered(T, (7, 2))


def test_faces_outside_the_opening_depth_stay(monkeypatch):
    T = carve(quad(z=-5.0), monkeypatch, '1')
    assert covered(T, (2, 2)) and covered(T, (7, 2))


def _tris(a, b, c):
    return np.array([[a, b, c]], float)


def planes(tris, up=(0, 1, 0), monkeypatch=None):
    class D:
        pass
    d = D(); d._up_view = np.asarray(up, float)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    return ViewDrawer._face_planes(d, tris, np.arange(len(tris)), n)


def test_vertical_face_is_unprojected():
    ((idx, M),) = planes(_tris([0, 0, 0], [4, 0, 0], [4, 3, 0]))
    assert M is None


def test_sloped_face_is_foreshortened_by_its_pitch():
    # 30 degree roof plane facing the viewer: along-slope length 2 projects to a height of 2 * sin(30)
    s, c = np.sin(np.radians(30)), np.cos(np.radians(30))
    T = _tris([0, 0, 0], [4, 0, 0], [4, 2 * s, -2 * c])
    ((idx, M),) = planes(T)
    assert M is not None and abs(M[0, 0] - 1) < 1e-6 and abs(M[1, 1] - s) < 1e-6 and abs(M[0, 1]) < 1e-6


def test_horizontal_face_is_unprojected():
    ((idx, M),) = planes(_tris([0, 0, 0], [4, 0, 0], [4, 0, -3]), up=(0, 1, 0))
    assert M is None
