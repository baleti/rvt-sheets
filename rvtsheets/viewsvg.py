"""view drawing (view coordinates, model feet) -> standalone SVG at the view scale (paper mm)"""
import html
import numpy as np
from .decode import FT_MM, color


def _rgb(c): return '#%02x%02x%02x' % tuple(int(a) for a in (c or [0, 0, 0])[:3])


MODEL_LAYERS = {'cut', 'projection', 'underlay', 'symbolic', 'symbolic_fill', 'cut_fill', 'surface_fill'}


def bounds(prims, model_only=True):
    """drawing extents; by default from the model layers only (Revit fits a view to its model extents; far annotations such as elevation
    markers do not enlarge it) - falls back to everything when a view has no model content"""
    if model_only:
        b = bounds([p for p in prims if p.get('layer') in MODEL_LAYERS], False)
        if b is not None: return b
    pts = []
    for p in prims:
        if p.get('pts'): pts += p['pts']
        for l in p.get('loops') or []: pts += l
        for s in p.get('segs') or []: pts += s
    if not pts: return None
    P = np.asarray(pts, float)[:, :2]
    return P.min(0), P.max(0)


def _inside(p, box):
    (u0, v0), (u1, v1) = box
    pts = p.get('pts') or [q for l in p.get('loops') or [] for q in l] + [q for sg in p.get('segs') or [] for q in sg] or ([p['origin']] if p.get('origin') else [])
    if not pts: return True
    P = np.asarray([q[:2] for q in pts], float)                    # bbox overlap: lines crossing the box with both ends outside (datums) stay
    lo = P.min(0); hi = P.max(0)
    return lo[0] <= u1 and hi[0] >= u0 and lo[1] <= v1 and hi[1] >= v0


def body(prims, scale, tx, layer_order=('underlay', 'room_fill', 'symbolic_fill', 'cut_fill', 'surface_fill', 'projection', 'cut', 'symbolic', 'annotation_fill'), clip=None):
    """svg elements; tx(u, v) -> paper mm (x, y)"""
    out = []
    def D(pts): return ' '.join(('M' if i == 0 else 'L') + '%.3f %.3f' % tx(*p[:2]) for i, p in enumerate(pts))
    def stroke(st):
        dash = ' stroke-dasharray="%s"' % ','.join('%.2f' % d for d in st['dash']) if st.get('dash') else ''
        return 'fill="none" stroke="%s" stroke-width="%.3f"%s stroke-linecap="round" stroke-linejoin="round"' % (_rgb(st['rgb']), max(st['w'], 0.05), dash)
    order = {k: i for i, k in enumerate(layer_order)}
    order['mask'] = -1
    if any('order' in p for p in prims):
        # detail draw order (views with m_aDrawOrder): model content first, then each detail element (its masking fills, hatches, lines)
        key = lambda p: (p.get('order', -2), order.get(p.get('layer'), 99))
    else: key = lambda p: order.get(p.get('layer'), 99)
    for p in sorted(prims, key=key):
        if clip is not None and not _inside(p, clip): continue
        e = ' data-e="%s"' % p.get('elem')
        if p['t'] == 'line': out.append('<path d="%s" %s%s/>' % (D(p['pts']), stroke(p['style']), e))
        elif p['t'] == 'segs': out.append('<path d="%s" %s%s/>' % (' '.join(D(s) for s in p['segs']), stroke(p['style']), e))
        elif p['t'] == 'cut':
            closed = [l for l in p['loops'] if len(l) > 3 and np.allclose(l[0], l[-1], atol=1e-6)]
            if closed and p.get('fill'): out.append('<path d="%s" fill="%s" fill-rule="evenodd" stroke="none"%s/>' % (' '.join(D(l) + ' Z' for l in closed), _rgb(p['fill']), e))
            out.append('<path d="%s" %s%s/>' % (' '.join(D(s) for s in p['segs']), stroke(p['style']), e))
        elif p['t'] == 'text' and p.get('text') and p.get('origin') is not None:
            out.append(text_svg(p, tx, scale))
        elif p['t'] == 'fill':
            c = color(p['color']) if isinstance(p.get('color'), int) else p.get('color')
            out.append('<path d="%s" fill="%s" fill-rule="evenodd" stroke="none"%s/>' % (' '.join(D(l) + ' Z' for l in p['loops']), _rgb(c) if c else '#888', e))
    return out


def view_svg(drawing, scale, margin_mm=5, crop=None):
    """crop: (u0, v0, u1, v1) of an active crop region - the drawing is bounded by it (Revit's own view export does the same)"""
    b = bounds(drawing['prims'])
    if b is None: return '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"/>'
    (u0, v0), (u1, v1) = b
    if crop is not None:
        cu0, cv0, cu1, cv1 = crop
        if max(u0, cu0) < min(u1, cu1) and max(v0, cv0) < min(v1, cv1):
            u0, v0, u1, v1 = max(u0, cu0), max(v0, cv0), min(u1, cu1), min(v1, cv1)
            # datum heads and bubbles (levels, grids) hang outside the crop region and are part of Revit's picture
            dp = [p for p in drawing['prims'] if p.get('layer') in ('datum',) or (p.get('t') == 'text' and p.get('elem') in {q.get('elem') for q in drawing['prims'] if q.get('layer') == 'datum'})]
            if dp:
                db = bounds(dp, False)
                if db is not None:
                    pad = 70.0 / (FT_MM / scale)                         # heads sit within ~70 mm of paper of the crop
                    (a0, b0), (a1, b1) = db
                    u0 = min(u0, max(a0, cu0 - pad)); v0 = min(v0, max(b0, cv0 - pad)); u1 = max(u1, min(a1, cu1 + pad)); v1 = max(v1, min(b1, cv1 + pad))
    k = FT_MM / scale
    W = (u1 - u0) * k + 2 * margin_mm; H = (v1 - v0) * k + 2 * margin_mm
    tx = lambda u, v: ((u - u0) * k + margin_mm, (v1 - v) * k + margin_mm)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%.1fmm" height="%.1fmm" viewBox="0 0 %.3f %.3f"><rect width="100%%" height="100%%" fill="#fff"/>\n' % (W, H, W, H)
            + '\n'.join(body(drawing['prims'], scale, tx, clip=((u0 - 2 * margin_mm / k, v0 - 2 * margin_mm / k), (u1 + 2 * margin_mm / k, v1 + 2 * margin_mm / k)))) + '\n</svg>\n')


def text_svg(p, tx, scale):
    """text prim in view coordinates (size in model feet) -> svg text"""
    import math
    from .decode import FT_MM
    x, y = tx(*p['origin'][:2])
    from .svg import EM, LINE_PITCH
    size_mm = (p.get('size') or 0.01) * FT_MM / scale * EM
    ang = -math.degrees(math.atan2(p['x'][1], p['x'][0])) if p.get('x') else 0.0
    if 85 < abs(ang) < 95 or ang < -95 or ang > 95:
        pass
    lines = p['text'].split('\n'); lh = size_mm * LINE_PITCH
    ha = {0: 'start', 1: 'middle', 2: 'end'}.get(p.get('halign') or 0, 'start')
    asc = size_mm * 0.9; n = len(lines)
    first = {0: asc, 1: asc - ((n - 1) * lh + asc) / 2, 2: -(n - 1) * lh}.get(p.get('valign') or 0, asc)
    tsp = ''.join('<tspan x="0" dy="%.3f">%s</tspan>' % ((first if i == 0 else lh), html.escape(l)) for i, l in enumerate(lines))
    wt = ' font-weight="bold"' if p.get('bold') else ''
    return '<text xml:space="preserve" transform="translate(%.3f %.3f) rotate(%.3f)" font-family="%s, sans-serif" font-size="%.3f" text-anchor="%s"%s data-e="%s">%s</text>' % (x, y, ang, html.escape(p.get('font') or 'Arial'), size_mm, ha, wt, p.get('elem'), tsp)
