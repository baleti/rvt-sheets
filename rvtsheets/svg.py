"""drawing dict (sheet feet coordinates, y up) -> SVG in paper millimetres (y down)."""
import html, math, os
from .decode import FT_MM, color

def line_pitch(font=None):
    """baseline-to-baseline in em: Arial 1.22, Trebuchet 1.26 (Snowdon cover sheet PDF: 3/32in notes 12 pt over 9.5 pt, titleblock addresses 8.4 mm over 6.7 mm)"""
    import os
    return 1.26 if 'trebuchet' in (font or '').lower() and os.environ.get('RVT_TEXTBASE', '1') == '1' else LINE_PITCH


LINE_PITCH = 1.22      # baseline-to-baseline distance in em (measured on the 2026 rosetta sheet export)
SHEET_MIN_W = float(os.environ.get('RVT_SHEET_MIN_W', '0.13'))      # sheet-level hairlines (titleblock grids, schedule rules) never thinner than ~0.13 mm: Revit's PNG shows them 1 px black, 0.076 mm pens anti-alias to light grey
EM = 1 / 0.72          # Revit 'Text Size' -> font em size (RTF \fs of 229 notes = 1.388 x type size)
FONT_MAP = {'Arial': "Arial, 'Liberation Sans', Arimo, Helvetica, sans-serif", 'Arial Narrow': "'Arial Narrow', 'Liberation Sans Narrow', 'Nimbus Sans Narrow', sans-serif",
            'Arial Black': "'Arial Black', Arial, 'Liberation Sans', sans-serif",
            'Trebuchet MS': "'Trebuchet MS', 'Noto Sans', 'Open Sans', Arial, sans-serif", 'Verdana': "Verdana, 'DejaVu Sans', sans-serif",
            'Georgia': "Georgia, 'Liberation Serif', Tinos, 'Times New Roman', serif", 'Times New Roman': "'Times New Roman', 'Liberation Serif', Tinos, serif",
            'Swis721 Lt BT': "'Swis721 Lt BT', Arial, 'Liberation Sans', sans-serif", 'ARchitxt': "Arial, 'Liberation Sans', sans-serif"}     # explicit fallback stacks (metric-compatible open fonts after the Revit font); proprietary fonts are never shipped


def revit_pt(size_mm):
    """rendered font size (paper mm) as Revit's PDF export prints it: the em (type size x EM) in points rounded UP to the next 0.5 pt (3/32" 9.375 -> 9.5,
    3/16" 18.75 -> 19.0), exact half points stay (1/8" 12.5, 1/4" 25.0, Arial 3/8" 37.5) except from 45 pt up where they move up by 0.5 (1/2" 50 -> 50.5,
    5/8" 62.5 -> 63.0, 1" 100 -> 100.5): measured on the Snowdon and Commercial PDFs (likely single-precision noise in Revit's conversion)"""
    import math, os
    if os.environ.get('RVT_PTSNAP', '1') != '1' or not size_mm: return size_mm
    pt = size_mm / (25.4 / 72)
    x2 = pt * 2
    if abs(x2 - round(x2)) < 2e-3: q = round(x2) / 2 + (0.5 if pt >= 45 else 0.0)
    else: q = math.ceil(x2) / 2
    return q * 25.4 / 72


# baseline of the first text line relative to the anchor, in em, as Revit's PDF export places it (Snowdon sheet / view PDFs vs the SVG anchor, per vertical alignment):
# top: baseline 0.98 em below the anchor, middle: 0.337 em ((ascent - descent) / 2), bottom: the descent above the anchor (Arial 0.225, Trebuchet 0.247)
BASE_OFF = {'trebuchet': (0.95, 0.335, 0.222), 'arial': (0.90, 0.338, 0.225)}      # absolute registration (sheet pages coincide): view titles Arial bottom 0.225, grid bubble digits middle 0.338, titleblock labels top 0.98


def box_slack(p, em, font=None):
    """half the free height (mm) of a label's text box over the font's natural line box (1.17 em Trebuchet, 1.15 em Arial): Revit centres the text in that slack for top and bottom aligned labels (Snowdon sheet S101 PDF: 'Parking' top +0.66 mm, 'Snowdon Towers' bottom -0.70 mm with box 1.77 x size; S000 boxes 1.625 x size sit at 0.0)"""
    import os
    from .decode import FT_MM
    if os.environ.get('RVT_TEXTBASE', '1') != '1' or os.environ.get('RVT_BOXSLACK', '1') != '1' or not p.get('box') or not p.get('label'): return 0.0
    nat = 1.17 if 'trebuchet' in (font or '').lower() else 1.15
    return (p['box'][1] * FT_MM - nat * em) / 2


def first_baseline(valign, n, lh, em, font=None, slack=0.0):
    """dy of the first line (mm) for an anchored text block: valign 0 top, 1 middle, 2 bottom"""
    import os
    if os.environ.get('RVT_TEXTBASE', '1') != '1':
        asc = em * 0.9
        return {0: asc, 1: asc - ((n - 1) * lh + asc) / 2, 2: -(n - 1) * lh}.get(valign or 0, asc)
    top, mid, bot = BASE_OFF['trebuchet' if 'trebuchet' in (font or '').lower() else 'arial']
    if (valign or 0) == 1: return mid * em - (n - 1) * lh / 2
    if valign == 2: return -(n - 1) * lh - bot * em - slack
    return top * em + slack


def rtf_first(em, font=None):
    """first baseline (mm) below the top of a saved-graphics rich-text box: Arial 0.90 em (Commercial cover sheet PDF), Trebuchet 0.99 em (Snowdon)"""
    import os
    if os.environ.get('RVT_TEXTBASE', '1') != '1': return em
    return em * (0.99 if 'trebuchet' in (font or '').lower() else 0.90)


def font_stack(name):
    import os
    if name in ('ARchitxt', 'Swis721 Lt BT') and os.environ.get('RVT_ARIAL_NARROW', 'arial') == 'arial': name = 'Arial'      # the Revit reference machines lack these fonts too and print Arial (Snowdon weld-symbol texts: Revit PDF = ArialMT)
    if name == 'Arial Narrow' and os.environ.get('RVT_ARIAL_NARROW', 'arial') == 'arial': name = 'Arial'      # the Revit machines that exported the reference PDFs have no Arial Narrow and print Arial (dimension texts of Snowdon L4: widths equal Arial Bold Italic, not the 18 % narrower Narrow); RVT_ARIAL_NARROW=real keeps the narrow face
    return FONT_MAP.get(name or 'Arial') or ("'%s', Arial, 'Liberation Sans', sans-serif" % name)


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
            self.parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.3f"%s stroke-linecap="round" stroke-linejoin="round"%s/>' % (self.path_d(p['pts']), _rgb(st['rgb']), max(st['w'], p.get('w_min') or 0.0, SHEET_MIN_W), dash, da))
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
        size_mm = revit_pt((p.get('size') or 0.0098) * FT_MM * EM)
        x, y = self.P(p['origin'])
        ang = 0.0
        if p.get('x'): ang = -math.degrees(math.atan2(p['x'][1], p['x'][0]))
        lines = p['text'].split('\n')
        ha = {0: 'start', 1: 'middle', 2: 'end'}.get(p.get('halign') or 0, 'start')
        lh = size_mm * line_pitch(p.get('font'))
        if p.get('anchor') and 'rtf' not in p:           # (a list-valued anchor = the control API's world point, not the alignment flag; saved-graphics rich text carries 'rtf')
            # notes/labels: origin is the anchor point on the alignment side; vertical: top / middle / bottom of the text block
            dx = 0.0
            bw_ = (p.get('box') or [0, 0])[0] * FT_MM
            if p.get('label') and bw_ > 1.0 and not p.get('nowrap') and os.environ.get('RVT_TB_LABELWRAP', '1') == '1' and (p.get('halign') or 0) == 0:
                from .viewdraw import wrap_text       # title block labels wrap at their layout box width (Residential cover: 'Enter address here' on two lines)
                lines = wrap_text('\n'.join(lines), bw_ / (p.get('width_scale') or 1.0), size_mm, p.get('font') or 'Arial', bool(p.get('bold'))).split('\n')
            n = len(lines)
            bh_ = (p.get('box') or [0, 0])[1] * FT_MM
            if p.get('label') and n > 1 and bh_ > 0 and bw_ > 1.0 and os.environ.get('RVT_TB_LABELWRAP', '1') == '1': lh = bh_ / n        # line pitch from the stored label box height
            first = first_baseline(p.get('valign'), n, lh, size_mm, p.get('font'), box_slack(p, size_mm, p.get('font')))
        else:
            # saved-graphics rich text: origin = top-left of the layout box (?), alignment inside the box
            bw = (p.get('box') or [0, 0])[0] * FT_MM
            dx = {0: 0, 1: bw / 2, 2: bw}.get(p.get('halign') or 0, 0) if bw else 0
            to_ = p.get('text_off') or [0, 0]; tbx = p.get('text_box') or [0, 0]
            if len(lines) == 1 and tbx[0] > 0 and to_[0] and os.environ.get('RVT_TB_TEXTOFF', '1') == '1':
                dx = to_[0] * FT_MM; ha = 'start'                 # Revit stores the aligned text's left edge inside the layout box (cover sheet URL: centred in the cell, not right-aligned)
            if len(lines) > 1 and tbx[1] > 0 and os.environ.get('RVT_TB_TEXTOFF', '1') == '1': lh = tbx[1] * FT_MM / len(lines)      # line pitch from the stored text height (consultant blocks 1.56 x size: 64 px not 69 px of the 3000 px cover sheet export)
            first = rtf_first(size_mm, p.get('font'))
            if bw > 1.0 and not p.get('nowrap') and p['text'].count(' ') >= 3:      # short labels ('Drawn By') overflow in a fallback font like Revit's does not wrap them
                # rich text in a layout box (title block labels): lines wrap at the box width like Revit's text
                from .viewdraw import wrap_text
                lines = wrap_text('\n'.join(lines), bw / (p.get('width_scale') or 1.0 if os.environ.get('RVT_TB_WS', '1') == '1' else 1.0), size_mm, p.get('font') or 'Arial', bool(p.get('bold'))).split('\n')
        fam = font_stack(p.get('font'))
        wt = ' font-weight="bold"' if p.get('bold') else ''
        it = ' font-style="italic"' if p.get('italic') else ''
        wsc = (p.get('width_scale') or 1.0) if os.environ.get('RVT_TB_WS', '1') == '1' else 1.0
        if abs(wsc - 1.0) > 1e-6: dx = dx / wsc
        tsp = ''.join('<tspan x="%.3f" dy="%.3f">%s</tspan>' % (dx, (first if i == 0 else lh), html.escape(l)) for i, l in enumerate(lines))
        self.parts.append('<text xml:space="preserve" transform="translate(%.3f %.3f) rotate(%.3f)%s" font-family="%s" font-size="%.3f" text-anchor="%s"%s%s fill="#000"%s>%s</text>' % (x, y, ang, (' scale(%.4f 1)' % wsc) if abs(wsc - 1.0) > 1e-6 else '', html.escape(fam), size_mm, ha, wt, it, da, tsp))

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
