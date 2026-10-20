import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.dimgeom import current_face, remeasured_value


def test_moved_face_nearest_low():
    # wall centre -91.0, half 0.4167: faces -91.4167 / -90.5833; stored point -91.25 (drift 0.1667) -> low face
    assert abs(current_face(-91.0, 0.4167, -91.25) - (-91.4167)) < 1e-9


def test_moved_face_nearest_high():
    assert abs(current_face(-100.125, 0.5, -99.75) - (-99.625)) < 1e-9


def test_unmoved_point_stays():
    assert current_face(19.2083, 0.5, 19.7083) is None          # exactly on the face
    assert current_face(19.2083, 0.5, 19.7083 + 5e-4) is None   # below tolerance


def test_too_far_is_not_a_face():
    assert current_face(0.0, 0.5, 0.0) is None                   # centre point: drift 0.5 > 0.9 * half
    assert current_face(0.0, 0.1, 0.5) is None                   # 0.4 from the face: drift > 0.9 * half = 0.09
    assert current_face(0.0, 0.0, 0.1) is None                   # no thickness


def test_max_drift_cap():
    assert current_face(0.0, 2.0, 1.0, max_drift=0.25) is None  # drift 1.0 > 0.25
    assert abs(current_face(0.0, 2.0, 1.9) - 2.0) < 1e-9        # drift 0.1


def test_remeasured_value():
    assert abs(remeasured_value([-99.625, -91.2917, 3.0], 0) - 8.3333) < 1e-4
    assert abs(remeasured_value([5.0, 2.0], 0) - 3.0) < 1e-12
