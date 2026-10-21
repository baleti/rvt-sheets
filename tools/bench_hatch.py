#!/usr/bin/env python3
"""Benchmark dash construction and full hatch, without test fixtures or data.

Run from a source checkout: python tools/bench_hatch.py --repeat 3
The construction speed-up isolates the optimized loop; full hatch also includes
GEOS clipping and conversion of the resulting geometry to Python lists.
"""
import argparse
import math
from pathlib import Path
import sys
import time

import numpy as np
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rvtsheets import patterns


def old_dash_endpoints(bases, tcs, R, d, segs, per, k, scale):
    """Original scalar loop, with the common line setup supplied by hatch."""
    ends = []
    for base, tc in zip(bases, tcs):
        t = math.floor((float(tc) - R) / per) * per
        while t < tc + R:
            for i, s_ in enumerate(segs):
                L = abs(s_)
                if i % 2 == 0:
                    ends.append((base + t * d,
                                 base + (t + (L if L > 1e-6 * k else
                                              patterns.DOT_MM / 304.8 * scale)) * d))
                t += L
    return np.asarray(ends, float).reshape(-1, 2, 2)


def measure(geom, pattern, build, repeat):
    original = patterns._dash_endpoints
    full_times, build_times = [], []
    captured = None

    def timed(*args):
        nonlocal captured
        start = time.perf_counter()
        result = build(*args)
        build_times.append(time.perf_counter() - start)
        captured = result
        return result

    try:
        patterns._dash_endpoints = timed
        for _ in range(repeat):
            start = time.perf_counter()
            output = patterns.hatch(geom, pattern, 48)
            full_times.append(time.perf_counter() - start)
    finally:
        patterns._dash_endpoints = original
    if captured is None or not len(captured) or not output:
        raise AssertionError('Benchmark must construct dashes, not use the fallback')
    return min(full_times), min(build_times), captured, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeat', type=int, default=3)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error('--repeat must be positive')
    geom = box(0, 0, 200, 200).difference(box(70, 70, 130, 130))
    cases = {
        'dash': [0.4, -0.4],
        'dot': [0.0, -0.8],
        'dash-dot': [0.3, -0.2, 0.0, -0.3],
        'six-segment': [0.2, -0.1, 0.0, -0.2, 0.2, -0.1],
    }
    print('200 x 200 ft polygon, 60 x 60 ft hole; best of', args.repeat)
    print('case          stage          old (s)    new (s)   speed-up')
    for name, segments in cases.items():
        pattern = {'target': 1, 'grids': [dict(
            angle=0.4, origin=[0.1, -0.2], shift=0.01,
            offset=1.0, segments=segments)]}
        old = measure(geom, pattern, old_dash_endpoints, args.repeat)
        new = measure(geom, pattern, patterns._dash_endpoints, args.repeat)
        np.testing.assert_allclose(new[2], old[2], rtol=0, atol=1e-9)
        np.testing.assert_allclose(new[3], old[3], rtol=0, atol=1e-9)
        for stage, index in [('construction', 1), ('full hatch', 0)]:
            print(f'{name:13} {stage:13} {old[index]:9.4f}  '
                  f'{new[index]:9.4f}  {old[index] / new[index]:8.2f}x')


if __name__ == '__main__':
    main()
