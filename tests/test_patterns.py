"""Characterize explicit hatch segments and the deliberately unclipped stipple dots."""
import math
import os
import sys

import numpy as np
import pytest
from shapely.geometry import LineString, Point, Polygon, box

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets import patterns


@pytest.fixture(autouse=True)
def reset_pattern_context(monkeypatch):
    for name in ("WORLD_UV", "ANCHOR", "CLIP"):
        monkeypatch.setattr(patterns, name, None)


def grid(angle=0, offset=1, origin=(0, 0), shift=0, segments=None):
    return dict(angle=angle, offset=offset, origin=origin, shift=shift,
                segments=segments)


def hatch(geom, grids=None, target=1, scale=1, view_rot=0):
    return patterns.hatch(geom, dict(target=target, grids=grids or [grid()]),
                          scale, view_rot)


def assert_segments(actual, expected):
    # GEOS may reverse or reorder pieces; compare endpoints without that detail.
    def canonical(segments):
        return sorted(tuple(sorted(tuple(round(v, 9) for v in p) for p in s))
                      for s in segments)
    assert canonical(actual) == canonical(expected)


@pytest.mark.parametrize("loops", [[], [[]], [[(0, 0), (1, 1)]],
    [[(0, 0), (1, 0), (2, 0)]], [[(0, 0), (1e-7, 0), (0, 1e-7)]],
    [[("bad", 0), (1, 0), (0, 1)]]])
def test_region_ignores_empty_degenerate_tiny_or_malformed_loops(loops):
    assert patterns.region(loops) is None


def test_region_uses_xy_and_even_odd_nested_loops():
    outer = [(0, 0, 99), (4, 0, 99), (4, 4, 99), (0, 4, 99)]
    hole = list(box(1, 1, 3, 3).exterior.coords)
    island = list(box(1.5, 1.5, 2.5, 2.5).exterior.coords)
    result = patterns.region([outer, hole, island])
    assert result.equals(box(0, 0, 4, 4).difference(box(1, 1, 3, 3)).union(
        box(1.5, 1.5, 2.5, 2.5)))
    assert result.area == 13


def test_region_duplicate_loops_cancel_to_empty_geometry():
    loop = list(box(0, 0, 2, 2).exterior.coords)
    result = patterns.region([loop, loop])
    assert result is not None
    assert result.is_empty
    assert hatch(result) == []


def test_region_repairs_self_intersection():
    result = patterns.region([[(0, 0), (2, 2), (0, 2), (2, 0)]])
    assert result.is_valid
    assert result.equals(Polygon([(0, 0), (1, 1), (2, 0)]))


@pytest.mark.parametrize("geom,pattern", [
    (None, {"grids": [grid()]}), (Polygon(), {"grids": [grid()]}),
    (box(0, 0, 1, 1), None), (box(0, 0, 1, 1), {}),
    (box(0, 0, 1, 1), {"solid": True, "grids": [grid()]}),
    (box(0, 0, 1, 1), {"grids": []}),
    (box(0, 0, 1, 1), {"grids": [grid(offset=0)]}),
    (box(0, 0, 1, 1), {"grids": [grid(segments=[0, 0])]}),
])
def test_hatch_empty_or_disabled(geom, pattern):
    assert patterns.hatch(geom, pattern, 1) == []


@pytest.mark.parametrize("offset", [1, -1])
def test_horizontal_spacing_origin_and_boundary_lines(offset):
    assert_segments(hatch(box(0, 0, 3, 2), [grid(offset=offset, origin=(8, 0.5))]),
                    [[[0, y], [3, y]] for y in (0.5, 1.5)])
    assert_segments(hatch(box(0, 0, 3, 2)),
                    [[[0, y], [3, y]] for y in (0, 1, 2)])


@pytest.mark.parametrize("angle,rotation", [(math.pi / 2, 0), (0, math.pi / 2),
                                           (math.pi / 4, math.pi / 4)])
def test_angle_and_view_rotation_add_but_origin_is_not_rotated(angle, rotation):
    result = hatch(box(0, 0, 3, 2), [grid(angle=angle, origin=(0.25, 0.5))],
                   view_rot=rotation)
    assert_segments(result, [[[x, 0], [x, 2]] for x in (0.25, 1.25, 2.25)])


@pytest.mark.parametrize("target,ys", [(0, (0.5, 2.5)), (1, (0.25, 1.25, 2.25, 3.25))])
def test_scale_affects_only_drafting_spacing_and_origin(target, ys):
    assert_segments(hatch(box(0, 0, 3, 4), [grid(origin=(0, 0.25))], target, 2),
                    [[[0, y], [3, y]] for y in ys])


def test_dashes_use_absolute_lengths_alternating_gaps_and_row_shift():
    result = hatch(box(0, 0, 4, 1.5), [grid(shift=0.5, segments=[-1, -1])])
    assert_segments(result, [[[0, 0], [1, 0]], [[2, 0], [3, 0]],
                            [[0.5, 1], [1.5, 1]], [[2.5, 1], [3.5, 1]]])


def test_drafting_scale_applies_to_dash_lengths_and_shift():
    result = hatch(box(0, 0, 7, 3), [grid(shift=0.5, segments=[1, -1])], 0, 2)
    assert_segments(result, [[[0, 0], [2, 0]], [[4, 0], [6, 0]],
                            [[1, 2], [3, 2]], [[5, 2], [7, 2]]])


def test_multiple_families_clip_at_holes_and_disjoint_components():
    geom = box(0, 0, 4, 4).difference(box(1, 1, 3, 3)).union(box(6, 0, 7, 1))
    result = hatch(geom, [grid(origin=(0, 0.5)), grid(angle=math.pi / 2, origin=(0.5, 0))])
    assert len(result) == 14  # Six pieces around the hole plus one island, per family.
    assert all(geom.buffer(1e-9).covers(LineString(s)) for s in result)
    assert_segments([s for s in result if all(abs(p[1] - 1.5) < 1e-9 for p in s)],
                    [[[0, 1.5], [1, 1.5]], [[3, 1.5], [4, 1.5]]])


def test_clip_context_restricts_hatching(monkeypatch):
    monkeypatch.setattr(patterns, "CLIP", box(1, 0.25, 2, 1.25))
    assert_segments(hatch(box(0, 0, 3, 3)), [[[1, 1], [2, 1]]])
    assert hatch(box(4, 4, 5, 5)) == []


@pytest.mark.parametrize("geom", [Point(0, 0), LineString([(0, 0), (1, 0)])])
def test_hatch_degenerate_geometry(geom):
    expected = [] if geom.geom_type == "Point" else [[[0, 0], [1, 0]]]
    assert_segments(hatch(geom), expected)


def test_stipple_seed_count_and_paper_dash_size():
    geom = box(0, 0, 1, 1)
    result = patterns.stipple(geom, 10, seed=23)
    assert result == patterns.stipple(geom, 10, seed=23)
    assert result != patterns.stipple(geom, 10, seed=24)
    assert len(result) == 46  # int(1 * (304.8 / 10)**2 * 0.05)
    assert len(patterns.stipple(geom, 20, seed=23)) == 11
    for start, end in result:
        assert geom.contains(Point(start))
        assert end[1] == start[1]
        assert end[0] - start[0] == pytest.approx(0.2 / 304.8 * 10)


@pytest.mark.parametrize("geom", [Polygon(), Point(0, 0),
    LineString([(0, 0), (1, 0)]), box(0, 0, 1e-6, 1e-6)])
def test_stipple_empty_zero_area_and_tiny_regions(geom):
    assert patterns.stipple(geom, 10) == []


def test_stipple_samples_inside_holes_but_does_not_clip_dash_ends():
    # Every dash is wider than this strip, so its endpoint must leave the region.
    geom = box(0, 0, 0.001, 100).difference(box(0, 30, 0.001, 60))
    result = patterns.stipple(geom, 10, seed=7)
    assert len(result) == 3
    assert all(geom.contains(Point(s[0])) for s in result)
    assert all(not geom.covers(LineString(s)) for s in result)


@pytest.mark.parametrize("target,rotation,expected", [
    (1, 0, [[[0, 0.25], [2, 0.25]], [[0, 1.25], [2, 1.25]]]),
    (0, 0, [[[0, 0], [2, 0]], [[0, 1], [2, 1]], [[0, 2], [2, 2]]]),
    (1, math.pi / 2, [[[0, 0], [0, 2]], [[1, 0], [1, 2]], [[2, 0], [2, 2]]]),
])
def test_world_origin_applies_only_to_unrotated_model_patterns(monkeypatch, target, rotation, expected):
    monkeypatch.setattr(patterns, "WORLD_UV", (0.25, 0.25))
    assert_segments(hatch(box(0, 0, 2, 2), target=target, view_rot=rotation), expected)


def test_model_anchor_replaces_normal_component_of_origin(monkeypatch):
    monkeypatch.setattr(patterns, "ANCHOR", (np.array([0., 1.]), 0.75))
    assert_segments(hatch(box(0, 0, 2, 2), [grid(origin=(0, 0.2))]),
                    [[[0, 0.75], [2, 0.75]], [[0, 1.75], [2, 1.75]]])


def test_zero_dash_becomes_paper_sized_dot_and_is_clipped():
    width = patterns.DOT_MM / 304.8 * 10
    result = hatch(box(0, 0, 2 + width / 2, 0.5),
                   [grid(segments=[0, 1])], scale=10)
    assert_segments(result, [[[0, 0], [width, 0]], [[1, 0], [1 + width, 0]],
                            [[2, 0], [2 + width / 2, 0]]])
