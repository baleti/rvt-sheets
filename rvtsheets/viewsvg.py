"""view drawing (view coordinates, model feet) -> standalone SVG at the view scale (paper mm)"""
import html, math, os
import numpy as np
from .decode import FT_MM, color
from .svg import font_stack


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


def body(prims, scale, tx, layer_order=('underlay', 'room_fill', 'symbolic_fill', 'cut_fill', 'surface_fill', 'projection', 'cut', 'symbolic', 'annotation_fill'), clip=None, mclip=False):
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
        if mclip and (p.get('layer') in MODEL_LAYERS or p.get('layer') == 'mask'): e += ' clip-path="url(#cropclip)"'      # model content is cut at the crop region (Revit shows nothing of it beyond)
        if p['t'] == 'line': out.append('<path d="%s" %s%s/>' % (D(p['pts']), stroke(p['style']), e))
        elif p['t'] == 'segs':
            segs_ = p['segs']
            if p.get('layer') in ('cut_fill', 'surface_fill', 'symbolic_fill') and abs(p['style'].get('w', 0) - 0.1) < 1e-6 and os.environ.get('RVT_DOTS', '1') == '1' and len(segs_) > 8:
                # stipple dots (dashes shorter than 0.5 mm on paper: Sand, Concrete specks) are drawn as 0.3 mm black dots like Revit's export (1 px at 3000 px sheets), not as 0.1 mm slivers
                dots, rest = [], []
                for sg in segs_:
                    (x0, y0), (x1, y1) = tx(*sg[0][:2]), tx(*sg[-1][:2])
                    (dots if math.hypot(x1 - x0, y1 - y0) < 0.5 else rest).append(sg)
                if dots:
                    st_ = dict(p['style'], w=0.34)
                    out.append('<path d="%s" %s%s/>' % (' '.join(D([[(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]] * 2) for a, b in ((sg[0], sg[-1]) for sg in dots)), stroke(st_), e))
                segs_ = rest
            if segs_: out.append('<path d="%s" %s%s/>' % (' '.join(D(s) for s in segs_), stroke(p['style']), e))
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


def view_svg(drawing, scale, margin_mm=5, crop=None, hang=True):
    """crop: (u0, v0, u1, v1) of an active crop region - the drawing is bounded by it (Revit's own view export does the same)"""
    b = bounds(drawing['prims'])
    if b is None: return '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"/>'
    (u0, v0), (u1, v1) = b
    hg = [p for p in drawing['prims'] if p.get('hang') or p.get('layer') in ('annotation', 'annotation_fill', 'text') and p.get('elem') is not None]
    hb_all = None
    if hang and hg:                                  # dimension chains, tags, notes and marker heads outside the model extents are part of Revit's picture (Residential plan 32 PNG)
        hb = bounds(hg, False)
        tp = []                                                          # text extents: origin and an estimated end of the longest line
        for q in hg:
            if q.get('t') == 'text' and q.get('origin') is not None and q.get('text'):
                o_ = np.asarray(q['origin'][:2], float); xd = np.asarray(q.get('x') or [1.0, 0.0], float)[:2]; wd = max(len(l) for l in q['text'].split('\n')) * 0.55 * (q.get('size') or 0.01) / 0.72
                tp += [o_, o_ + xd / (np.linalg.norm(xd) or 1.0) * wd * (-1 if q.get('halign') == 2 else 1), o_ + [0.0, -(q.get('size') or 0.01) * 1.2 * q['text'].count('\n')]]
        if tp:
            T_ = np.asarray(tp, float)
            hb = (T_.min(0), T_.max(0)) if hb is None else (np.minimum(hb[0], T_.min(0)), np.maximum(hb[1], T_.max(0)))
        if hb is not None:
            pad = 1e4 / (FT_MM / scale)                              # no limit: Revit's view picture holds every annotation (colour scheme legend 100 mm right of the plan)
            (a0, b0), (a1, b1) = hb
            hb_all = (a0, b0, a1, b1)
            if crop is None: u0 = min(u0, max(a0, u0 - pad)); v0 = min(v0, max(b0, v0 - pad)); u1 = max(u1, min(a1, u1 + pad)); v1 = max(v1, min(b1, v1 + pad))
    if crop is not None:
        cu0, cv0, cu1, cv1 = crop
        if max(u0, cu0) < min(u1, cu1) and max(v0, cv0) < min(v1, cv1):
            u0, v0, u1, v1 = max(u0, cu0), max(v0, cv0), min(u1, cu1), min(v1, cv1)
            # datum heads and bubbles (levels, grids) hang outside the crop region and are part of Revit's picture
            dp = [p for p in drawing['prims'] if p.get('layer') in ('datum',) or p.get('hang') or (p.get('t') == 'text' and p.get('elem') in {q.get('elem') for q in drawing['prims'] if q.get('layer') == 'datum'})]
            if dp:
                db = bounds(dp, False)
                if db is not None:
                    pad = 70.0 / (FT_MM / scale)                         # heads sit within ~70 mm of paper of the crop
                    (a0, b0), (a1, b1) = db
                    u0 = min(u0, max(a0, cu0 - pad)); v0 = min(v0, max(b0, cv0 - pad)); u1 = max(u1, min(a1, cu1 + pad)); v1 = max(v1, min(b1, cv1 + pad))
    if crop is not None and hb_all is not None:                  # annotations outside the crop region (colour scheme legend, tags, dimension chains) stay in the picture
        u0 = min(u0, hb_all[0]); v0 = min(v0, hb_all[1]); u1 = max(u1, hb_all[2]); v1 = max(v1, hb_all[3])
    k = FT_MM / scale
    W = (u1 - u0) * k + 2 * margin_mm; H = (v1 - v0) * k + 2 * margin_mm
    tx = lambda u, v: ((u - u0) * k + margin_mm, (v1 - v) * k + margin_mm)
    defs = ''; mc = False
    if crop is not None:
        x0_, y1_ = tx(crop[0], crop[1]); x1_, y0_ = tx(crop[2], crop[3])
        defs = '<defs><clipPath id="cropclip"><rect x="%.3f" y="%.3f" width="%.3f" height="%.3f"/></clipPath></defs>\n' % (min(x0_, x1_), min(y0_, y1_), abs(x1_ - x0_), abs(y1_ - y0_)); mc = True
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%.1fmm" height="%.1fmm" viewBox="0 0 %.3f %.3f"><rect width="100%%" height="100%%" fill="#fff"/>\n' % (W, H, W, H) + defs
            + '\n'.join(body(drawing['prims'], scale, tx, clip=((u0 - 2 * margin_mm / k, v0 - 2 * margin_mm / k), (u1 + 2 * margin_mm / k, v1 + 2 * margin_mm / k)), mclip=mc)) + '\n</svg>\n')


def text_svg(p, tx, scale):
    """text prim in view coordinates (size in model feet) -> svg text"""
    import math, os
    from .decode import FT_MM
    x, y = tx(*p['origin'][:2])
    from .svg import EM, LINE_PITCH, line_pitch, revit_pt, first_baseline, rtf_first, box_slack
    size_mm = revit_pt((p.get('size') or 0.01) * FT_MM / scale * EM)
    ang = -math.degrees(math.atan2(p['x'][1], p['x'][0])) if p.get('x') else 0.0
    if 85 < abs(ang) < 95 or ang < -95 or ang > 95:
        pass
    lines = p['text'].split('\n'); lh = size_mm * line_pitch(p.get('font'))
    ha = {0: 'start', 1: 'middle', 2: 'end'}.get(p.get('halign') or 0, 'start')
    asc = size_mm * 0.9; n = len(lines); dx = 0.0
    if p.get('anchor') and 'rtf' not in p: first = first_baseline(p.get('valign'), n, lh, size_mm, p.get('font'), box_slack(p, size_mm, p.get('font')))
    else:
        # saved-graphics rich text (family labels such as the Help Button '?'): origin = top-left of the layout box, alignment inside the box
        bw = (p.get('box') or [0, 0])[0] * FT_MM / scale
        dx = {0: 0.0, 1: bw / 2, 2: bw}.get(p.get('halign') or 0, 0.0) if bw else 0.0
        first = rtf_first(size_mm, p.get('font'))
    tsp = ''.join('<tspan x="%.3f" dy="%.3f">%s</tspan>' % (dx, (first if i == 0 else lh), html.escape(l)) for i, l in enumerate(lines))
    wt = ' font-weight="bold"' if p.get('bold') else ''
    c = p.get('color'); fill = ''
    if isinstance(c, int) and 0 < c < 1 << 24: fill = ' fill="#%02x%02x%02x"' % (c & 255, (c >> 8) & 255, (c >> 16) & 255)       # text colour (BGR int): the Help Button '?' is light grey on blue
    wsc = p.get('width_scale') or 1.0
    wtr = (' scale(%.4f 1)' % wsc) if abs(wsc - 1.0) > 1e-6 else ''       # text type 'Width Factor' (wide / condensed notes): horizontal scale about the anchor
    return '<text xml:space="preserve" transform="translate(%.3f %.3f) rotate(%.3f)%s" font-family="%s" font-size="%.3f" text-anchor="%s"%s%s data-e="%s">%s</text>' % (x, y, ang, wtr, html.escape(font_stack(p.get('font'))), size_mm, ha, wt, fill, p.get('elem'), tsp)
