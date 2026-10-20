import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.areapoly import boundary_polygons


def square(offset):
    # clockwise 10 x 10 square: the interior is on the RIGHT of the travel direction, so a positive offset (towards the right) moves a line inward, a negative one outward (Revit boundary lines: -0.3125 = outward)
    L = [((0, 0), (1, 0), 0, 10, offset), ((10, 0), (0, -1), 0, 10, offset), ((10, -10), (-1, 0), 0, 10, offset), ((0, -10), (0, 1), 0, 10, offset)]
    return L


def test_plain_square():
    ps = boundary_polygons(square(0.0), [])
    assert len(ps) == 1 and abs(ps[0].area - 100.0) < 1e-6


def test_outward_offset():
    ps = boundary_polygons(square(-0.5), [])
    assert len(ps) == 1 and abs(ps[0].area - 121.0) < 1e-4


def test_inward_offset():
    ps = boundary_polygons(square(0.5), [])
    assert len(ps) == 1 and abs(ps[0].area - 81.0) < 1e-4


def test_empty():
    assert boundary_polygons([], []) == []


def test_arc_cap():
    # D shape: a straight base and a half circle (radius 5) above it, counter clockwise
    lines = [((-5, 0), (1, 0), 0, 10, 0.0)]
    arcs = [((0, 0), 5.0, (1, 0), (0, 1), 0.0, math.pi, 0.0)]
    ps = boundary_polygons(lines, arcs)
    assert len(ps) == 1 and abs(ps[0].area - math.pi * 25 / 2) < 0.2


def test_arc_offset_radius_ccw():
    lines = [((-5, 0), (1, 0), 0, 10, 0.0)]
    a0 = [((0, 0), 5.0, (1, 0), (0, 1), 0.0, math.pi, 0.0)]
    a1 = [((0, 0), 5.0, (1, 0), (0, 1), 0.0, math.pi, 0.5)]  # CCW arc: radius + offset
    p0 = boundary_polygons(lines, a0)[0].area
    # a moved CCW arc grows its radius by the offset; the base line is untouched (offset 0) but extended by 0.55, polygon still closes
    p1 = boundary_polygons(lines, a1)
    assert p1 and p1[0].area > p0
