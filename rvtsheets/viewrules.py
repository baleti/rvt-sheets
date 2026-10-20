"""Pure decisions about whether elements may be listed in a view."""


def property_line_candidate(kind, plan_view_type, range_top, crop_z_far, legacy=False, bbox_z=None, range_bottom=None, range_depth=None):
    """True when a property line segment may be listed in the view.

    kind is 'plan', 'section', '3d', etc.; plan_view_type is 1 for a floor
    plan, 2 for a ceiling plan, or None. Heights are in feet. range_top
    may be None or effectively unbounded (e.g. 1e9). crop_z_far is the
    first crop-volume z bound, or None/0.

    The legacy rule tests bbox_z against the view range with a 1e-6
    tolerance; missing bottom and depth bounds mean no lower limit.
    Bounding-box presence and crop intersection are checked by the caller.
    """
    if kind != 'plan':
        return False
    if legacy:
        if plan_view_type == 2 or range_top is None or bbox_z is None:
            return False
        zlo = min((z for z in (range_bottom, range_depth) if z is not None),
                  default=float('-inf'))
        return zlo - 1e-6 <= bbox_z <= range_top + 1e-6
    site = (range_top is not None and range_top >= 100
            and plan_view_type != 2 and range_top < 1e8)
    return (crop_z_far or 0) >= 999 or site
