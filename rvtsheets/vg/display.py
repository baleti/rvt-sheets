"""Pure drawing rules for Revit view display settings."""

STYLES = {
    1: 'wireframe',
    2: 'hidden',
    3: 'shaded',
    4: 'shaded_edges',      # codes = Autodesk DisplayStyle enum + 1 (oracle verified 1, 2, 3, 7; 4, 6, 8 follow the enum, seen in real files)
    5: 'realistic',
    6: 'raytrace',
    7: 'consistent',
    8: 'rendering',
}


def display_style(surfaces) -> str:
    """Resolve an integer surface code, defaulting to hidden line display."""
    if not isinstance(surfaces, (int, str)):
        return 'hidden'
    try:
        code = int(surfaces)
    except ValueError:
        return 'hidden'
    return STYLES.get(code, 'hidden')


def drawing_rules(style, kind, discipline=None) -> dict:
    """Return display flags, treating unknown kinds as plan views."""
    if style not in STYLES.values():
        style = 'hidden'

    is_3d = kind == '3d'
    occlude = style != 'wireframe' or (not is_3d and discipline == 2)
    return {
        'occlude': occlude,
        'cut_caps': occlude,
        'surface_fills': style != 'wireframe',
        'shaded_faces': is_3d and style in ('shaded', 'shaded_edges', 'realistic', 'raytrace', 'consistent', 'rendering'),
    }
