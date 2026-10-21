"""Text placement for a leaderless spot elevation in the view frame."""

import math

import numpy as np


def place(a, off, Mv, ang, dirx, scale, neg_enabled=True):
    """Return the text origin in view feet and alignment (0=start, 2=end).

    a is a (2,) point in view feet, off is the (3,) stored text offset,
    and Mv is the (3, 3) model-to-view matrix. ang is the text angle in
    radians; dirx is the picked beam direction's view-frame x component.
    scale is the view scale (96 means 1/8 inch = 1 foot); 0 or None means 1.
    neg_enabled enables the negative-offset placement adjustments.
    """
    sc = scale or 1
    ca, sa = math.cos(ang), math.sin(ang)
    rot = abs(ang) > 0.5
    neg = off[1] < 0 and rot and neg_enabled
    endh = off[1] < 0 and not rot and dirx < -0.5 and neg_enabled
    o0 = -off[0] if neg else off[0]
    b = np.asarray(a, dtype=float) + (
        Mv @ np.array([
            -(ca * o0 - sa * off[1]),
            sa * o0 + ca * off[1],
            off[2],
        ])
    )[:2]
    if neg:
        b += np.array([1, 0]) * (0.0115 * sc) + np.array([ca, sa]) * (-0.0034 * sc)
    elif rot:
        b += np.array([-0.003, -0.0085]) * sc
    elif endh:
        b += np.array([ca, sa]) * (0.0197 * sc)
    else:
        b += np.array([ca, sa]) * (0.0115 * sc)
    halign = 0 if ((abs(ang) < 0.5 and not endh) or neg) else 2
    return b, halign
