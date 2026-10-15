"""drawing dict (sheet feet coordinates, y up) -> SVG in paper millimetres (y down)."""
import html, math
from .decode import FT_MM, color

LINE_PITCH = 1.22      # baseline-to-baseline distance in em (measured on the 2026 rosetta sheet export)
EM = 1 / 0.72          # Revit 'Text Size' -> font em size (RTF \fs of 229 notes = 1.388 x type size)
FONT_MAP = {'Arial': 'Arial, Liberation Sans, Helvetica, sans-serif', 'Arial Narrow': "'Arial Narrow', 'Liberation Sans Narrow', sans-serif"}


def _rgb(c):
    if not c: return '#000'
    return '#%02x%02x%02x' % tuple(int(a) for a in c[:3])


class SVG:
    def __init__(self, extent, styler=None, margin_mm=0):
        x0, y0, x1, y1 = extent
        self.x0, self.y1 = x0, y1
        self.w = (x1 - x0) * FT_MM; self.h = (y1 - y0) * FT_MM
        self.sty = styler; self.parts = []

    def P(self, p):
        return ((p[0] - self.x0) * FT_MM, (self.y1 - p[1]) * FT_MM)

    def path_d(self, pts, close=False):
        s = ' '.join(('M' if i == 0 else 'L') + '%.3f %.3f' % self.P(p) for i, p in enumerate(pts))
        return s + (' Z' if close else '')

    def prim(self, p, style=None):
        t = p['t']; eid = p.get('elem')
        da = ' data-e="%s"' % eid if eid is not None else ''
        if t == 'line':
            st = style or (self.sty.line(p.get('gs')) if self.sty else {'w': 0.18, 'rgb': [0, 0, 0], 'dash': None})
            dash = ' stroke-dasharray="%s"' % ','.join('%.2f' % d for d in st['dash']) if st.get('dash') else ''
            self.parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.3f"%s stroke-linecap="round" stroke-linejoin="round"%s/>' % (self.path_d(p['pts']), _rgb(st['rgb']), max(st['w'], 0.05), dash, da))
        elif t == 'fill':
            d = ' '.join(self.path_d(l, True) for l in (p.get('loops') or []) if l)
            if not d: return
            c = color(p['color']) if isinstance(p.get('color'), int) else p.get('color')
            self.parts.append('<path d="%s" fill="%s" fill-rule="evenodd" stroke="none"%s/>' % (d, _rgb(c), da))
        elif t == 'text':
            self.text(p, da)
        elif t == 'image' and p.get('uri'):
            cx, cy = p['center']; w, h = p['w'], p['h']
            a = self.P((cx - w / 2, cy + h / 2))
            rot = ''
            if abs(p.get('angle') or 0) > 1e-3:
                c = self.P((cx, cy)); rot = ' transform="rotate(%.3f %.3f %.3f)"' % (-math.degrees(p['angle']), c[0], c[1])
            self.parts.append('<image x="%.3f" y="%.3f" width="%.3f" height="%.3f" href="%s" preserveAspectRatio="none"%s%s/>' % (a[0], a[1], w * FT_MM, h * FT_MM, p['uri'], rot, da))

    def text(self, p, da=''):
        if not p.get('text') or p.get('origin') is None: return
        size_mm = (p.get('size') or 0.0098) * FT_MM * EM
        x, y = self.P(p['origin'])
        ang = 0.0
        if p.get('x'): ang = -math.degrees(math.atan2(p['x'][1], p['x'][0]))
        lines = p['text'].split('\n')
        ha = {0: 'start', 1: 'middle', 2: 'end'}.get(p.get('halign') or 0, 'start')
        lh = size_mm * LINE_PITCH
        if p.get('anchor'):
            # notes/labels: origin is the anchor point on the alignment side; vertical: top / middle / bottom of the text block
            dx = 0.0
            n = len(lines); asc = size_mm * 0.9
            first = {0: asc, 1: asc - ((n - 1) * lh + asc) / 2, 2: -(n - 1) * lh}.get(p.get('valign') or 0, asc)
        else:
            # saved-graphics rich text: origin = top-left of the layout box (?), alignment inside the box
            bw = (p.get('box') or [0, 0])[0] * FT_MM
            dx = {0: 0, 1: bw / 2, 2: bw}.get(p.get('halign') or 0, 0) if bw else 0
            first = size_mm
            if bw > 1.0 and not p.get('nowrap'):
                # rich text in a layout box (title block labels): lines wrap at the box width like Revit's text
                from .viewdraw import wrap_text
                lines = wrap_text('\n'.join(lines), bw, size_mm, p.get('font') or 'Arial', bool(p.get('bold'))).split('\n')
        fam = FONT_MAP.get(p.get('font') or 'Arial', "'%s', sans-serif" % p.get('font'))
        wt = ' font-weight="bold"' if p.get('bold') else ''
        it = ' font-style="italic"' if p.get('italic') else ''
        tsp = ''.join('<tspan x="%.3f" dy="%.3f">%s</tspan>' % (dx, (first if i == 0 else lh), html.escape(l)) for i, l in enumerate(lines))
        self.parts.append('<text xml:space="preserve" transform="translate(%.3f %.3f) rotate(%.3f)" font-family="%s" font-size="%.3f" text-anchor="%s"%s%s fill="#000"%s>%s</text>' % (x, y, ang, html.escape(fam), size_mm, ha, wt, it, da, tsp))

    def rect(self, x0, y0, x1, y1, stroke='#999', w=0.25, dash='2,1'):
        a = self.P((x0, y1)); b = self.P((x1, y0))
        self.parts.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="none" stroke="%s" stroke-width="%.2f" stroke-dasharray="%s"/>' % (a[0], a[1], b[0] - a[0], b[1] - a[1], stroke, w, dash))

    def raw(self, s): self.parts.append(s)

    def tostring(self):
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="%.2fmm" height="%.2fmm" viewBox="0 0 %.3f %.3f">\n<rect width="100%%" height="100%%" fill="#fff"/>\n' % (self.w, self.h, self.w, self.h)
                + '\n'.join(self.parts) + '\n</svg>\n')


def drawing_svg(dr, styler):
    s = SVG(dr['extent'], styler)
    for p in dr['prims']: s.prim(p)
    for vp in dr.get('viewports', []):
        c = vp.get('content')
        if c: s.raw(c(s) if callable(c) else c)
        else:
            o = vp['vp']['offset']
            s.raw('<circle cx="%.2f" cy="%.2f" r="2" fill="none" stroke="#c00" stroke-width="0.3"/>' % s.P(o))
            s.text({'text': '%s (1:%s)' % (vp['view']['name'], vp['view']['scale']), 'origin': [o[0], o[1] - 0.02, 0], 'size': 2.5 / FT_MM})
    return s.tostring()
