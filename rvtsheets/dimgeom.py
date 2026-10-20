"""Pure geometry helpers for re-measuring dimension references."""


def current_face(centre, half, stored, tol=1e-3, max_drift=0.25):
    """Return the nearest face if its drift is allowed, otherwise None.

    Ties select the lower face. Nonpositive thickness, drift at or below
    tol, and drift above min(max_drift, 0.9 * half) do not move the point.
    """
    if half <= 0:
        return None
    face = min((centre - half, centre + half), key=lambda x: abs(x - stored))
    drift = abs(face - stored)
    if tol < drift <= min(max_drift, 0.9 * half):
        return float(face)
    return None


def remeasured_value(positions, i):
    """Return the absolute span of refs i and i+1 in stored order."""
    return abs(positions[i + 1] - positions[i])
