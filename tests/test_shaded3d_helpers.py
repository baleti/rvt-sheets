"""Synthetic numeric tests; no Decoder, Revit data, or optional JIT required.

Projection and lighting live inside render, rather than separate helpers.
The clipping helpers require viewdraw, absent from this source-only checkout.
Load a private module with an identity njit decorator to exercise the actual
Python raster algorithm without compilation time or a Numba dependency.
"""
import importlib.util
import io
from pathlib import Path
import sys
import types

import numpy as np
from PIL import Image
import pytest


@pytest.fixture(scope="module")
def shaded():
    path = Path(__file__).resolve().parents[1] / "rvtsheets" / "shaded3d.py"
    spec = importlib.util.spec_from_file_location("_shaded3d_numeric_tests", path)
    module = importlib.util.module_from_spec(spec)
    stub = types.ModuleType("numba")
    stub.njit = lambda **kwargs: lambda function: function
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "numba", stub)
        spec.loader.exec_module(module)
    return module


TRI = np.array([[[-1., -1., 2.], [1., -1., 2.], [-1., 1., 2.]]])


def render(shaded, triangles=TRI, colors=None, alphas=None, **kwargs):
    options = dict(eye=np.zeros(3), right=np.array([1., 0., 0.]),
                   up=np.array([0., 1., 0.]), fwd=np.array([0., 0., 1.]),
                   tan_x=1., tan_y=1., width_px=16, sun=(0., 0., -1.),
                   sky=((0, 0, 0), (0, 0, 0)))
    options.update(kwargs)
    count = len(triangles)
    colors = np.tile([200., 100., 40.], (count, 1)) if colors is None else colors
    alphas = np.ones(count) if alphas is None else alphas
    png, w, h = shaded.render(triangles, np.asarray(colors), alphas, **options)
    with Image.open(io.BytesIO(png)) as image:
        assert image.mode == "RGB"
        pixels = np.array(image)
    assert pixels.shape == (h, w, 3)
    assert pixels.dtype == np.uint8
    return pixels, png, (w, h)


def raster(shaded, depths, colors, alphas=None, vertices=None):
    count = len(depths)
    vertices = np.tile([[0., 0.], [4., 0.], [0., 4.]], (count, 1, 1)) if vertices is None else np.asarray(vertices, float)
    image = np.full((5, 5, 3), 20, np.uint8)
    buffer = np.full((5, 5), -1.)
    shaded._raster(vertices[:, :, 0], vertices[:, :, 1], np.asarray(depths, float),
                   np.asarray(colors, np.uint8), np.ones(count) if alphas is None else np.asarray(alphas, float),
                   5, 5, buffer, image)
    return image, buffer


@pytest.mark.parametrize("perspective", [True, False])
def test_known_projection_coordinates(shaded, monkeypatch, perspective):
    captured = []
    monkeypatch.setattr(shaded, "_raster", lambda *args: captured.append(args))
    triangles = np.array([[[0., 0., 2.], [2., 0., 4.], [0., 2., 2.]]])
    _, _, size = render(shaded, triangles, perspective=perspective,
                        ortho_half=(2., 1.), tan_y=.5, centre=(.25, .125))
    assert size == (16, 8)
    x, y, inverse_depth = captured[0][:3]
    np.testing.assert_allclose(x, [[6, 10, 6]] if perspective else [[7, 15, 7]])
    np.testing.assert_allclose(y, [[5, 5, -3]] if perspective else [[4.5, 4.5, -3.5]])
    np.testing.assert_allclose(inverse_depth, [[.5, .25, .5]])


def test_translated_rotated_camera(shaded):
    baseline = render(shaded)[0]
    # Cyclic axis permutation is a rigid rotation, including the light.
    rotation = np.array([[0., 1., 0.], [0., 0., 1.], [1., 0., 0.]])
    eye = np.array([10., -4., 7.])
    actual = render(shaded, TRI @ rotation + eye, eye=eye,
                    right=rotation[0], up=rotation[1], fwd=rotation[2],
                    sun=-rotation[2])[0]
    np.testing.assert_array_equal(actual, baseline)
    assert np.any(actual)


def test_two_sided_lighting_and_winding(shaded):
    lit = render(shaded)[0]
    reversed_face = render(shaded, TRI[:, ::-1].copy())[0]
    dark = render(shaded, sun=(0., 0., 1.))[0]
    np.testing.assert_array_equal(lit, reversed_face)
    np.testing.assert_array_equal(lit[9, 5], [200, 100, 40])
    np.testing.assert_array_equal(dark[9, 5], [90, 45, 18])
    assert np.all(lit[9, 5] > dark[9, 5])
    np.testing.assert_array_equal(render(shaded, sun=(0., 0., -7.))[0], lit)


def test_gain_clamps_channels(shaded):
    pixels = render(shaded, gain=2.)[0]
    np.testing.assert_array_equal(pixels[9, 5], [255, 200, 80])
    np.testing.assert_array_equal(render(shaded, gain=0.)[0], 0)


@pytest.mark.parametrize("reverse", [False, True])
def test_opaque_depth_order(shaded, reverse):
    depths = np.array([[.25] * 3, [.5] * 3])
    colors = np.array([[200, 0, 0], [0, 200, 0]])
    if reverse:
        depths, colors = depths[::-1], colors[::-1]
    pixels, buffer = raster(shaded, depths, colors)
    np.testing.assert_array_equal(pixels[0, 0], [0, 200, 0])
    assert buffer[0, 0] == .5
    assert buffer[4, 4] == -1
    np.testing.assert_array_equal(pixels[4, 4], [20, 20, 20])


def test_inverse_depth_interpolated_at_pixel_centres(shaded):
    _, buffer = raster(shaded, [[1., .5, .25]], [[100, 0, 0]])
    # At (.5,.5), barycentric weights are (.75,.125,.125).
    assert buffer[0, 0] == pytest.approx(.84375)
    assert buffer[0, 2] == pytest.approx(.59375)
    assert np.count_nonzero(buffer > 0) == 10


def test_equal_depth_keeps_first_opaque_face(shaded):
    pixels, _ = raster(shaded, [[.5]*3, [.5]*3], [[100, 0, 0], [0, 100, 0]])
    np.testing.assert_array_equal(pixels[0, 0], [100, 0, 0])


@pytest.mark.parametrize("alpha,expected", [(0., [20, 20, 20]), (.25, [65, 40, 25]), (1., [200, 100, 40])])
def test_alpha_blending_and_depth_writes(shaded, alpha, expected):
    pixels, buffer = raster(shaded, [[.5]*3], [[200, 100, 40]], [alpha])
    np.testing.assert_array_equal(pixels[0, 0], expected)
    assert buffer[0, 0] == (.5 if alpha == 1 else -1.)


def test_transparency_behind_opaque_is_hidden(shaded):
    pixels, buffer = raster(shaded, [[.5]*3, [.25]*3], [[100, 0, 0], [0, 100, 0]], [1., .5])
    np.testing.assert_array_equal(pixels[0, 0], [100, 0, 0])
    assert buffer[0, 0] == .5


def test_render_orders_opaque_before_glass(shaded):
    triangles = np.concatenate([TRI, TRI * 2])
    colors = np.array([[200., 0., 0.], [0., 100., 0.]])
    actual = render(shaded, triangles, colors, [.5, 1.])[0]
    reversed_order = render(shaded, triangles[::-1], colors[::-1], [1., .5])[0]
    np.testing.assert_array_equal(actual[9, 5], [100, 50, 0])
    np.testing.assert_array_equal(actual, reversed_order)


@pytest.mark.parametrize("vertices", [
    [[[1., 1.], [1., 1.], [1., 1.]]],
    [[[0., 0.], [2., 2.], [4., 4.]]],
    [[[-10., -10.], [-8., -10.], [-10., -8.]]],
])
def test_degenerate_and_offscreen_triangles(shaded, vertices):
    pixels, buffer = raster(shaded, [[.5]*3], [[255, 0, 0]], vertices=vertices)
    np.testing.assert_array_equal(pixels, 20)
    np.testing.assert_array_equal(buffer, -1.)


@pytest.mark.parametrize("depth", [-2., 0., .1])
def test_near_plane_drops_triangle_with_one_invalid_vertex(shaded, depth):
    triangles = TRI.copy()
    triangles[0, 0, 2] = depth
    with np.errstate(divide="raise", invalid="raise"):
        pixels = render(shaded, triangles)[0]
    np.testing.assert_array_equal(pixels, 0)


def test_empty_scene_sky_and_minimum_height(shaded):
    empty = np.empty((0, 3, 3))
    pixels, png, size = render(shaded, empty, sky=((10, 20, 30), (30, 40, 50)), tan_y=.5)
    assert size == (16, 8)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    np.testing.assert_array_equal(pixels[0, 0], [10, 20, 30])
    np.testing.assert_array_equal(pixels[-1, -1], [30, 40, 50])
    assert render(shaded, empty, tan_y=.001)[2] == (16, 1)


def test_determinism_and_input_preservation(shaded):
    triangles = TRI.copy()
    colors = np.array([[200., 100., 40.]])
    alphas = np.array([1.])
    first = render(shaded, triangles, colors, alphas)
    second = render(shaded, triangles, colors, alphas)
    assert first[1] == second[1]
    np.testing.assert_array_equal(first[0], second[0])
    np.testing.assert_array_equal(triangles, TRI)
    np.testing.assert_array_equal(colors, [[200., 100., 40.]])
    np.testing.assert_array_equal(alphas, [1.])
