"""DepthBuffer.paint: flat colour only where the group is the nearest surface (no corpus)"""
import os, sys, io
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.hlr import DepthBuffer


def tri(w, x0=0.0, y0=0.0, s=10.0): return np.array([[[x0, y0, w], [x0 + s, y0, w], [x0, y0 + s, w]]], float)


def decode(png):
    from PIL import Image
    return np.asarray(Image.open(io.BytesIO(png)).convert('RGBA'))


def test_visible_group_is_painted_and_window_is_tight():
    db = DepthBuffer(0, 0, 10, 10, 0.1)
    t = tri(5.0); db.add(t)
    png, (u0, v0, u1, v1) = db.paint([(t, (255, 0, 0, 255))], 0.05)
    im = decode(png)
    assert im[:, :, 3].any() and (im[im[:, :, 3] > 0][:, :3] == [255, 0, 0]).all()
    assert u0 <= 0.1 and v0 <= 0.1 and u1 >= 9.9 and v1 >= 9.9 and u1 - u0 < 11


def test_occluded_group_is_not_painted():
    db = DepthBuffer(0, 0, 10, 10, 0.1)
    far = tri(1.0); near = tri(5.0); db.add(far); db.add(near)
    assert db.paint([(far, (0, 255, 0, 255))], 0.05) is None
    assert db.paint([(near, (0, 0, 255, 255))], 0.05) is not None


def test_empty_groups_give_none():
    db = DepthBuffer(0, 0, 10, 10, 0.1)
    assert db.paint([], 0.05) is None
    assert db.paint([(np.zeros((0, 3, 3)), (1, 2, 3, 255))], 0.05) is None


def test_alpha_is_kept():
    db = DepthBuffer(0, 0, 10, 10, 0.1)
    t = tri(5.0); db.add(t)
    png, _ = db.paint([(t, (10, 20, 30, 128))], 0.05)
    a = decode(png)[:, :, 3]
    assert set(np.unique(a)) <= {0, 128} and (a == 128).any()
