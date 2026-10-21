"""Small, synthetic examples for the source-only geometry and view helpers."""

import math

import pytest

from rvtsheets.areapoly import boundary_polygons
from rvtsheets.dimgeom import current_face, remeasured_value
from rvtsheets.viewrules import property_line_candidate


def _edges(vertices, offset=0.0):
    """Encode a closed path using unit directions and distance parameters."""
    result = []
    for start, end in zip(vertices, vertices[1:] + vertices[:1]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        result.append((start, (dx / length, dy / length), 0, length, offset))
    return result


@pytest.mark.parametrize("offset, side", [(0, 4), (0.5, 5), (-0.5, 3)])
def test_square_offsets(offset, side):
    polygons = boundary_polygons(_edges([(0, 0), (4, 0), (4, 4), (0, 4)], offset), [])
    assert len(polygons) == 1
    polygon = polygons[0]
    assert polygon.is_valid
    assert polygon.area == pytest.approx(side ** 2)
    assert polygon.bounds == pytest.approx((-offset, -offset, 4 + offset, 4 + offset))


@pytest.mark.parametrize("offset, area", [(0, 7), (0.5, 16), (-0.25, 3.25)])
def test_concave_l_offsets(offset, area):
    vertices = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)]
    polygons = boundary_polygons(_edges(vertices, offset), [])
    assert len(polygons) == 1
    assert polygons[0].is_valid
    assert polygons[0].area == pytest.approx(area)


def test_empty_and_open_boundaries():
    assert boundary_polygons([], []) == []
    assert boundary_polygons([((0, 0), (1, 0), 0, 4, 0)], []) == []
    assert boundary_polygons(_edges([(0, 0), (4, 0), (4, 4), (0, 4)])[:-1], []) == []


def test_disconnected_squares_and_unordered_reversed_edges():
    first = _edges([(0, 0), (2, 0), (2, 2), (0, 2)])
    second = _edges([(10, 10), (13, 10), (13, 13), (10, 13)])
    # Endpoint order and curve order must not affect polygonization.
    reversed_edges = [(o, d, t1, t0, off) for o, d, t0, t1, off in first]
    polygons = boundary_polygons((reversed_edges + second)[::-1], [])
    assert len(polygons) == 2
    assert sorted(p.area for p in polygons) == pytest.approx([4, 9])


def test_nonzero_line_parameters():
    lines = [((-2, 0), (1, 0), 2, 6, 0),
             ((4, -2), (0, 1), 2, 6, 0),
             ((6, 4), (-1, 0), 2, 6, 0),
             ((0, 6), (0, -1), 2, 6, 0)]
    polygons = boundary_polygons(lines, [])
    assert len(polygons) == 1
    assert polygons[0].area == pytest.approx(16)


@pytest.mark.parametrize("handedness", [1, -1])
def test_full_circle_translated_rotated_basis(handedness):
    arc = ((7, -3), 2, (0, 1), (-handedness, 0), 0, 2 * math.pi, 0)
    polygons = boundary_polygons([], [arc])
    assert len(polygons) == 1
    assert polygons[0].is_valid
    # Arcs are polygonal approximations; allow their chord discretization error.
    assert polygons[0].area == pytest.approx(4 * math.pi, rel=0.001)
    assert (polygons[0].centroid.x, polygons[0].centroid.y) == pytest.approx((7, -3), abs=1e-4)


@pytest.mark.parametrize("handedness, offset, radius", [(1, 0.5, 2.5), (-1, 0.5, 1.5)])
def test_offset_semicircle_with_diameter(handedness, offset, radius):
    arc = ((0, 0), 2, (1, 0), (0, handedness), 0, math.pi, offset)
    diameter = ((-3, 0), (1, 0), 0, 6, 0)
    polygons = boundary_polygons([diameter], [arc])
    assert len(polygons) == 1
    assert polygons[0].is_valid
    assert polygons[0].area == pytest.approx(math.pi * radius ** 2 / 2, rel=0.001)


@pytest.mark.parametrize("changes, expected", [
    ({}, False),
    ({"kind": "section", "crop_z_far": 1000}, False),
    ({"kind": "3d", "range_top": 200}, False),
    ({"range_top": 99.999}, False),
    ({"range_top": 100}, True),
    ({"range_top": 1e8 - 1}, True),
    ({"range_top": 1e8}, False),
    ({"range_top": 1e9}, False),
    ({"range_top": 100, "plan_view_type": 2}, False),
    ({"range_top": 100, "plan_view_type": None}, True),
    ({"crop_z_far": 0}, False),
    ({"crop_z_far": 998.999}, False),
    ({"crop_z_far": 999}, True),
    ({"crop_z_far": 999, "plan_view_type": 2}, True),
])
def test_modern_view_predicate(changes, expected):
    view = dict(kind="plan", plan_view_type=1, range_top=None, crop_z_far=None)
    view.update(changes)
    assert property_line_candidate(**view) is expected


@pytest.mark.parametrize("changes, expected", [
    ({}, True),
    ({"kind": "section"}, False),
    ({"plan_view_type": 2}, False),
    ({"range_top": None}, False),
    ({"bbox_z": None}, False),
    ({"bbox_z": -1e10}, True),
    ({"bbox_z": 10 + 0.5e-6}, True),
    ({"bbox_z": 10 + 2e-6, "crop_z_far": 1000}, False),
    ({"range_bottom": 2, "bbox_z": 1}, False),
    ({"range_depth": 2, "bbox_z": 1}, False),
    ({"range_bottom": 2, "range_depth": -2, "bbox_z": -1}, True),
    ({"range_bottom": -2, "range_depth": 2, "bbox_z": -1}, True),
    ({"range_bottom": 2, "bbox_z": 2 - 0.5e-6}, True),
    ({"range_bottom": 2, "bbox_z": 2 - 2e-6}, False),
])
def test_legacy_view_predicate(changes, expected):
    view = dict(kind="plan", plan_view_type=1, range_top=10,
                crop_z_far=None, legacy=True, bbox_z=5)
    view.update(changes)
    assert property_line_candidate(**view) is expected


@pytest.mark.parametrize("centre, half, stored, options, expected", [
    (0, 0, 0.1, {}, None),
    (0, -1, 0.1, {}, None),
    (0, 1, 1, {}, None),
    (1, 1, 0.001, {}, None),
    (0, 1, 1.0005, {}, None),
    (0, 1, 1.1, {}, 1.0),
    (0, 1, -0.9, {}, -1.0),
    (0, 1, 1.25, {}, 1.0),
    (0, 1, 1.2501, {}, None),
    (0, 0.1, 0.02, {}, 0.1),
    (0, 0.1, 0.005, {}, None),
    (0, 1, 0, {}, None),
    (0, 1, 1.1, {"tol": 0.2}, None),
    (0, 1, 1.4, {"max_drift": 0.5}, 1.0),
    (0, 1, 1.1, {"max_drift": 0.05}, None),
    (10, 2, 8.125, {}, 8.0),
])
def test_current_face_drift_limits(centre, half, stored, options, expected):
    result = current_face(centre, half, stored, **options)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)
        assert isinstance(result, float)


@pytest.mark.parametrize("positions, index, expected", [
    ([1, 4], 0, 3),
    ([4, 1], 0, 3),
    ([-5, -2], 0, 3),
    ([-2, 3], 0, 5),
    ([7, 7], 0, 0),
    ([10, 2, 7], 0, 8),
    ([10, 2, 7], 1, 5),
    ((0.125, 0.375), 0, 0.25),
])
def test_remeasured_value_preserves_reference_order(positions, index, expected):
    assert remeasured_value(positions, index) == pytest.approx(expected)
