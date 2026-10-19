import numpy as np
from rvtsheets.shaded3d import _clip_attr


def test_clip_attr_keeps_attributes():
    T = np.array([[[0, 0, 0], [2, 0, 0], [0, 2, 0]],          # straddles x + y <= 1
                  [[5, 5, 5], [6, 5, 5], [5, 6, 5]]], float)  # wholly outside
    C = np.array([[10, 20, 30], [1, 2, 3]], float); A = np.array([1.0, 0.5]); K = np.array([7, 8])
    n = np.array([1.0, 1.0, 0.0]) / np.sqrt(2)
    T2, C2, A2, K2 = _clip_attr(T, C, A, K, n, 1.0 / np.sqrt(2))
    assert len(T2) == len(C2) == len(A2) == len(K2) >= 1
    assert set(K2.tolist()) == {7} and (A2 == 1.0).all() and (C2 == [10, 20, 30]).all()
    assert (T2 @ n <= 1.0 / np.sqrt(2) + 1e-9).all()


def test_clip_attr_whole_triangles_pass():
    T = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], float)
    T2, C2, A2, K2 = _clip_attr(T, np.ones((1, 3)), np.ones(1), np.array([3]), np.array([0, 0, 1.0]), 5.0)
    assert len(T2) == 1 and K2.tolist() == [3]
