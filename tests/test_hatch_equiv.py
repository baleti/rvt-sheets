"""fuzz: rvtsheets.patterns.hatch == frozen reference (tests/_patterns_ref.py) on random dashed / continuous patterns"""
import os, sys, random
import numpy as np
from shapely.geometry import Polygon, box
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rvtsheets import patterns as new
import _patterns_ref as ref


def norm(segs):
    return sorted((round(a[0], 6), round(a[1], 6), round(b[0], 6), round(b[1], 6)) for a, b in segs)


def rand_pattern(rng):
    grids = []
    for _ in range(rng.randint(1, 3)):
        nseg = rng.choice([0, 2, 2, 4, 6])
        segs = [rng.choice([0.0, 0.02, 0.05, 0.1]) if i % 2 == 0 else -rng.choice([0.03, 0.08, 0.2]) for i in range(nseg)]
        grids.append({'angle': rng.uniform(0, 3.14159), 'origin': [rng.uniform(-1, 1), rng.uniform(-1, 1)], 'shift': rng.choice([0.0, 0.01, 0.05]),
                      'offset': rng.choice([0.05, 0.1, 0.25]), 'segments': segs})
    return {'solid': False, 'target': rng.choice([0, 1]), 'grids': grids}


def test_random_patterns_match_reference():
    rng = random.Random(1234)
    geoms = [box(0, 0, 12, 7), Polygon([(0, 0), (9, 1), (11, 8), (2, 6)]), box(0, 0, 8, 8).difference(box(2, 2, 5, 5))]
    for n in range(60):
        pat = rand_pattern(rng); g = geoms[n % 3]; scale = rng.choice([1, 8, 48, 96]); vr = rng.choice([0.0, 0.3])
        a = new.hatch(g, pat, scale, vr); b = ref.hatch(g, pat, scale, vr)
        assert norm(a) == norm(b), (n, pat)


def test_guards_and_empty_inputs_match():
    pat = {'solid': False, 'target': 0, 'grids': [{'angle': 0.0, 'origin': [0, 0], 'shift': 0.0, 'offset': 0.001, 'segments': [0.0, -0.001]}]}
    g = box(0, 0, 400, 400)
    assert norm(new.hatch(g, pat, 1)) == norm(ref.hatch(g, pat, 1))
    assert new.hatch(None, pat, 1) == [] and new.hatch(box(0, 0, 1, 1), {'solid': True}, 1) == []


def test_dash_dot_is_faster_than_reference():
    """a case under MAX_DASHES (both versions really build the dashes): full hatch() includes the shapely clip, which bounds the end-to-end gain (~1.5x when the dash loop is 40x faster)"""
    import time
    pat = {'solid': False, 'target': 1, 'grids': [{'angle': 0.4, 'origin': [0, 0], 'shift': 0.0, 'offset': 0.25, 'segments': [0.04, -0.03, 0.0, -0.03]},
                                                   {'angle': 1.2, 'origin': [0.1, 0.0], 'shift': 0.01, 'offset': 0.25, 'segments': [0.05, -0.05]}]}
    g = box(0, 0, 60, 60).difference(box(20, 20, 30, 30))
    assert not (len(new.hatch(box(0, 0, 1, 1), pat, 1)) == 0), 'sanity: the pattern produces segments'
    def best(fn, n=3):
        t = []
        for _ in range(n):
            t0 = time.perf_counter(); out = fn(g, pat, 1); t.append(time.perf_counter() - t0)
        return min(t), out
    tr, a = best(ref.hatch); tn, b = best(new.hatch)
    assert len(a) > 50000, 'the benchmark must really build dashes (got %d segments)' % len(a)
    assert norm(a) == norm(b)
    assert tr / tn >= 1.3, 'speed-up %.2fx (ref %.3fs, new %.3fs)' % (tr / tn, tr, tn)
