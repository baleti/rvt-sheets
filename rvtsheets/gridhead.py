"""Choose the head end of a datum line in view coordinates."""

import numpy as np


def order_ends(uv0, uv1, cls, view_kind, grid_ext, has_extent, on_x,
               xvec_z, gridnorth=False, xflip=True):
    """Return independent float arrays (head end, other end).

    uv0 and uv1 are (2,) line ends in view coordinates, with y up.
    Only cls='Grid' is reordered; other classes behave like 'Level'.
    grid_ext preserves ends fixed by per-view / 3D extents, while
    has_extent indicates a stored per-view extent record. on_x means
    the line runs along the datum surface's xVec; xvec_z is its z component.
    """
    uv0 = np.array(uv0, dtype=float, copy=True)
    uv1 = np.array(uv1, dtype=float, copy=True)

    if grid_ext:
        return uv0, uv1
    elif cls == 'Grid' and view_kind == 'section' and uv0[1] < uv1[1]:
        uv0, uv1 = uv1, uv0

    if cls == 'Grid' and not has_extent and view_kind == 'plan':
        dv = uv1 - uv0
        if (abs(dv[1]) >= abs(dv[0])
                and uv0[1] < uv1[1]
                and (not on_x or gridnorth)
                and not (xflip and xvec_z < -0.9)):
            uv0, uv1 = uv1, uv0

    return uv0, uv1
