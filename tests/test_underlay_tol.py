"""ViewDrawer.underlay: a floor whose top face lies exactly on the underlay's lower plane (Residential attic: level-30 floors at z 0) keeps its edges"""
import collections
import numpy as np
from rvtsheets.viewdraw import ViewDrawer


class _Res:
    def line(self, *a, **k): return {}


def slab(z0, z1):
    a = [[0, 0], [10, 0], [10, 5], [0, 5]]
    top = [[x, y, z1] for x, y in a]; bot = [[x, y, z0] for x, y in a]
    T = [[top[0], top[1], top[2]], [top[0], top[2], top[3]], [bot[0], bot[2], bot[1]], [bot[0], bot[3], bot[2]]]
    for i in range(4):
        j = (i + 1) % 4
        T += [[bot[i], bot[j], top[j]], [bot[i], top[j], top[i]]]
    return np.array(T, float)


def run(top_z, lo=0.0, hi=9.0):
    d = ViewDrawer.__new__(ViewDrawer); d.stats = collections.Counter()
    out = d.underlay([(1, -2000032, slab(top_z - 1.0, top_z), np.arange(12), 1, {})], (lo, hi), 0.2, 96, _Res())
    return out, d.stats


def test_top_face_on_lower_plane_kept():
    out, st = run(0.0)
    assert st['underlay_elements'] == 1 and out and out[0]['segs']


def test_body_wholly_below_lower_plane_dropped():
    out, st = run(-0.5)
    assert not out
