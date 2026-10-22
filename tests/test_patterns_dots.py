"""zero-length dashes touching a drawn dash are not drawn as dots (Revit 'Brick Brownsville Soldier': dash 0.83, gap 0, dash 0, gap 0)"""
import numpy as np
from shapely.geometry import box
from rvtsheets import patterns


def test_real_dashes_mask():
    assert list(patterns._real_dashes(np.array([0.83, 0.0, 0.0, 0.0]), 1e-9)) == [True, False]
    assert list(patterns._real_dashes(np.array([0.5, 0.5, 0.0, 0.5]), 1e-9)) == [True, True]      # a real stipple dot keeps its gaps


def test_soldier_has_no_dot_segments():
    pat = {'name': 'x', 'target': 1, 'solid': False, 'grids': [
        {'angle': 0.0, 'origin': [0.0, 0.03125], 'shift': 0.0, 'offset': 0.8333333333, 'segments': []},
        {'angle': 1.5707963267948, 'origin': [0.0, 0.03125], 'shift': 0.0, 'offset': 0.2083333333, 'segments': [0.8333333333, 0.0, 0.0, 0.0]}]}
    segs = patterns.hatch(box(0, 0, 1.7, 1.7), pat, 96)
    vert = {}
    for a, b in segs:
        if abs(a[0] - b[0]) < 1e-9: vert.setdefault(round(a[0], 6), []).append(sorted((a[1], b[1])))
    for ivs in vert.values():          # one drawn line per pattern column: no dot overlapping a dash
        ivs.sort()
        assert all(ivs[i][1] <= ivs[i + 1][0] + 1e-9 for i in range(len(ivs) - 1))
