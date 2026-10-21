"""Small synthetic scenes for the public DepthBuffer API (no model corpus)."""

from io import BytesIO

import numpy as np
from PIL import Image
import pytest

from rvtsheets.hlr import DepthBuffer


def triangle(z=1.0):
    return np.array([[[0., 0., z], [4., 0., z], [0., 4., z]]])


def segment(z, x0=0.5, x1=1.5, y=1.0):
    return np.array([[[x0, y, z], [x1, y, z]]])


def scene():
    return DepthBuffer(-2, -2, 6, 6, 0.1)


def decode(result):
    data, bounds = result
    with Image.open(BytesIO(data)) as image:
        assert image.mode == "RGBA"
        return np.array(image), bounds


@pytest.mark.parametrize("z", [-1.0, 0.0, 0.9])
def test_segments_behind_triangle_are_hidden(z):
    db = scene()
    db.add(triangle())
    assert db.visible_parts(segment(z), eps=0.0) == []
    # The same depth remains visible away from the triangle footprint.
    outside = segment(z, x0=4.5, x1=5.5)
    parts = db.visible_parts(outside, eps=0.0)
    assert len(parts) == 1
    np.testing.assert_array_equal(parts[0], outside[0])


@pytest.mark.parametrize("z", [1.0, 1.1, 2.0])
def test_segments_on_or_in_front_of_face_are_whole(z):
    db = scene()
    db.add(triangle())
    seg = segment(z)
    parts = db.visible_parts(seg, eps=1e-12)
    assert len(parts) == 1
    np.testing.assert_array_equal(parts[0], seg[0])
    assert np.linalg.norm(parts[0][1] - parts[0][0]) == pytest.approx(1.0)


def test_epsilon_accepts_small_depth_difference_but_not_large_one():
    db = scene()
    db.add(triangle())
    seg = segment(0.95)
    assert db.visible_parts(seg, eps=0.01) == []
    parts = db.visible_parts(seg, eps=0.06)
    assert len(parts) == 1
    np.testing.assert_array_equal(parts[0], seg[0])
    assert db.visible_parts(segment(0.8), eps=0.06) == []


def test_exact_epsilon_boundary_and_exact_face():
    # Binary-exact depths and barycentric weights on this integer pixel grid
    # avoid mistaking roundoff for a failure of the inclusive comparison.
    db = DepthBuffer(0, 0, 4, 4, 0.5)
    db.add(triangle())
    assert len(db.visible_parts(segment(0.875), eps=0.125)) == 1
    assert db.visible_parts(segment(0.875), eps=0.124) == []
    assert len(db.visible_parts(segment(1.0), eps=0.0)) == 1


def test_crossing_segment_has_two_visible_runs():
    db = scene()
    db.add(triangle())
    seg = segment(0.0, x0=-1.0, x1=5.0)
    parts = db.visible_parts(seg, eps=0.0)
    assert len(parts) == 2
    lengths = [np.linalg.norm(b - a) for a, b in parts]
    # At y=1 the geometric occluder spans x=0..3. The 3x3 pixel
    # neighbourhood expands it, and sample bins quantize the endpoints.
    assert lengths[0] == pytest.approx(1.0, abs=2 * db.px)
    assert lengths[1] == pytest.approx(2.0, abs=2 * db.px)
    assert sum(lengths) < 3.0
    np.testing.assert_array_equal(parts[0][0], seg[0, 0])
    np.testing.assert_array_equal(parts[-1][1], seg[0, 1])
    assert parts[0][1][0] < parts[1][0][0]
    np.testing.assert_array_equal(np.asarray(parts)[:, :, 1:], [[[1, 0], [1, 0]]] * 2)
    reversed_parts = db.visible_parts(seg[:, ::-1], eps=0.0)
    np.testing.assert_allclose(reversed_parts, np.asarray(parts)[::-1, ::-1], atol=1e-12)


def test_empty_scene_and_empty_inputs():
    db = scene()
    before = db.zb.copy()
    db.add([])
    db.add(np.empty((0, 3, 3)))
    np.testing.assert_array_equal(db.zb, before)
    segs = np.concatenate([segment(-100), segment(100, 20, 21)])
    parts = db.visible_parts(segs, eps=0.0)
    assert len(parts) == 2
    np.testing.assert_array_equal(parts, segs)
    assert db.visible_parts([], eps=0.0) == []
    assert db.paint([], eps=0.0) is None
    assert db.paint([(np.empty((0, 3, 3)), (1, 2, 3, 255))], eps=0.0) is None


@pytest.mark.parametrize("vertices", [
    [[1, 1, 5], [1, 1, 5], [1, 1, 5]],
    [[0, 0, 5], [1, 1, 5], [2, 2, 5]],
    [[0, 0, 1], [0, 0, 5], [2, 2, 3]],
])
def test_projected_degenerate_triangles_do_not_occlude_or_paint(vertices):
    db = scene()
    tris = np.array([vertices], dtype=float)
    before = db.zb.copy()
    db.add(tris)
    np.testing.assert_array_equal(db.zb, before)
    parts = db.visible_parts(segment(0), eps=0.0)
    assert len(parts) == 1
    np.testing.assert_array_equal(parts[0], segment(0)[0])
    assert db.paint([(tris, (13, 57, 91, 180))], eps=0.0) is None


def test_rgba_paint_shape_coverage_and_vertical_orientation():
    db = DepthBuffer(0, 0, 4, 4, 1.0)
    db.add(triangle())
    colour = (13, 57, 91, 180)
    image, bounds = decode(db.paint([(triangle(), colour)], eps=0.0))
    assert image.shape == (5, 5, 4)
    assert image.dtype == np.uint8
    assert bounds == (0.0, 0.0, 5.0, 5.0)
    # Pixel centres (x+.5, y+.5) lie in the triangle iff x+y <= 3.
    y, x = np.indices((5, 5))
    covered = (x + y <= 3)[::-1]
    assert covered.sum() == 10
    np.testing.assert_array_equal(image[covered], np.tile(colour, (10, 1)))
    np.testing.assert_array_equal(image[~covered], np.zeros((15, 4), dtype=np.uint8))
    np.testing.assert_array_equal(image[-1, 0], colour)
    np.testing.assert_array_equal(image[0, 0], [0, 0, 0, 0])
    assert db.paint([(triangle(0), colour)], eps=0.0) is None


def test_determinism_winding_order_and_repeated_adds():
    tris = np.concatenate([triangle(0), triangle(1)])
    first, second = scene(), scene()
    first.add(tris)
    second.add(tris[::-1, ::-1])
    np.testing.assert_allclose(first.zb, second.zb, atol=1e-12, rtol=0)
    before = first.zb.copy()
    first.add(tris)
    np.testing.assert_array_equal(first.zb, before)
    segs = np.concatenate([segment(0, -1, 5), segment(2)])
    parts = first.visible_parts(segs, eps=0.01)
    np.testing.assert_array_equal(first.visible_parts(segs, eps=0.01), parts)
    np.testing.assert_allclose(second.visible_parts(segs, eps=0.01), parts)
    groups = [(tris, (23, 45, 67, 210))]
    painted = first.paint(groups, eps=0.01)
    assert painted is not None
    assert first.paint(groups, eps=0.01) == painted
    assert second.paint(groups, eps=0.01) == painted
    np.testing.assert_array_equal(first.zb, before)
