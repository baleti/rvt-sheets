"""PDF export of sheets: the cached sheet SVGs (paper size in mm) -> one PDF page each through rsvg-convert (cairo, vector).
CLI:  rvt-sheets pdf FILE.rvt OUT.pdf [SHEET_NUMBER...]   (all sheets by default, in sheet-number order; missing drawings are rendered)
The server serves GET /api/{mid}/sheet/{id}.pdf and /api/{mid}/sheets.pdf from the same function."""
import os, sys, re, html, shutil, subprocess, tempfile

_TEXT_SCALED = re.compile(r'<text\b([^>]*?)transform="([^"]*?)scale\(([\d.]+) 1\)"([^>]*)>(.*?)</text>', re.S)
_FONT = {}


def _font(bold=False):
    if bold not in _FONT:
        from fontTools.ttLib import TTFont
        f = ''
        if shutil.which('fc-match'): f = subprocess.run(['fc-match', '-f', '%{file}', 'Arial:bold' if bold else 'Arial'], capture_output=True, text=True).stdout.strip()
        if not f:
            from . import _plat; f = _plat.fonts().find('Arial', bold=bold) or ''
        _FONT[bold] = TTFont(f)
    return _FONT[bold]


def _text_path(txt, size, anchor, bold):
    """SVG path data (y down, origin at the baseline start) of a string in Arial at the given size"""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    f = _font(bold); gs = f.getGlyphSet(); cmap = f.getBestCmap(); hmtx = f['hmtx']; k = size / f['head'].unitsPerEm
    names = [cmap.get(ord(c), '.notdef') for c in txt]; w = sum(hmtx[n][0] for n in names) * k
    x = -w / 2 if anchor == 'middle' else -w if anchor == 'end' else 0.0
    pen = SVGPathPen(gs)
    for n in names:
        gs[n].draw(TransformPen(pen, (k, 0, 0, -k, x, 0))); x += hmtx[n][0] * k
    return pen.getCommands()


def flatten_scaled_text(svg):
    """cairo's PDF backend squeezes text carrying a non-uniform scale (width factor: the glyph advances are not scaled): such strings become glyph outlines"""
    def rep(m):
        pre, tr, sx, post, body = m.groups()
        if abs(float(sx) - 1) < 0.3: return m.group(0)                 # mild width factors (0.85) survive cairo's squeeze visibly unharmed; outlines look heavier at small sizes
        attrs = pre + post
        try:
            size = float(re.search(r'font-size="([\d.]+)"', attrs).group(1)); fill = (re.search(r'fill="([^"]*)"', attrs) or [None, '#000'])[1]
            anchor = (re.search(r'text-anchor="(\w+)"', attrs) or [None, 'start'])[1]; bold = 'font-weight="bold"' in attrs or 'font-weight="700"' in attrs
            tsp = re.findall(r'<tspan([^>]*)>(.*?)</tspan>', body, re.S)
            if not tsp: tsp = [('', body)]
            d = []; y = 0.0
            for a, t in tsp:
                dy = re.search(r'dy="([-\d.]+)"', a); y += float(dy.group(1)) if dy else 0.0
                x = re.search(r'\bx="([-\d.]+)"', a); x = float(x.group(1)) if x else 0.0
                t = html.unescape(re.sub(r'<[^>]+>', '', t))
                if t.strip(): d.append('<path transform="translate(%g %g)" d="%s"/>' % (x, y, _text_path(t, size, anchor, bold)))
            return '<g transform="%sscale(%s 1)" fill="%s">%s</g>' % (tr, sx, fill, ''.join(d))
        except Exception: return m.group(0)
    return _TEXT_SCALED.sub(rep, svg)


def _svgs_to_pdf_browser(svg_files, out_pdf):
    """no rsvg-convert (Windows / macOS): one vector PDF per sheet through headless Edge/Chrome, merged with pypdf when there are several"""
    from . import _plat
    R = _plat.render()
    if not R.browser.find(): raise RuntimeError('rsvg-convert not installed and no Chromium-family browser found (set RVT_BROWSER)')
    tdir = tempfile.mkdtemp(prefix='svgpdf'); parts = []
    try:
        for i, f in enumerate(svg_files):
            t = open(f, encoding='utf-8').read(); g = flatten_scaled_text(t)
            if g != t: f = os.path.join(tdir, '%d.svg' % i); open(f, 'w', encoding='utf-8').write(g)
            parts.append(R.svg_to_pdf(f, os.path.join(tdir, '%d.pdf' % i)))
        if len(parts) == 1: data = open(parts[0], 'rb').read()
        else:
            try: from pypdf import PdfWriter, PdfReader
            except ImportError: raise RuntimeError('several sheets without rsvg-convert need pypdf (pip install pypdf)')
            w = PdfWriter()
            for q in parts:
                for pg in PdfReader(q).pages: w.add_page(pg)
            import io; b = io.BytesIO(); w.write(b); data = b.getvalue()
        _plat.fsio().atomic_write(out_pdf, data)
    finally: shutil.rmtree(tdir, ignore_errors=True)
    return out_pdf


def svgs_to_pdf(svg_files, out_pdf):
    """several SVG files -> one multi-page PDF (each page at the SVG's own width/height)"""
    if not shutil.which('rsvg-convert'): return _svgs_to_pdf_browser(svg_files, out_pdf)
    tmp = out_pdf + '.%d.tmp' % os.getpid()
    tdir = tempfile.mkdtemp(prefix='svgpdf'); files = []
    try:
        for i, f in enumerate(svg_files):
            t = open(f, encoding='utf-8').read(); g = flatten_scaled_text(t)
            if g != t: f = os.path.join(tdir, '%d.svg' % i); open(f, 'w', encoding='utf-8').write(g)
            files.append(f)
        subprocess.run(['rsvg-convert', '-f', 'pdf', '-o', tmp] + files, check=True, capture_output=True, timeout=600)
    finally: shutil.rmtree(tdir, ignore_errors=True)
    os.replace(tmp, out_pdf)
    return out_pdf


def model_pdf(m, sheet_ids, out_pdf):
    """m: drawings.Model; renders sheets that are not cached yet, then writes the PDF; returns out_pdf"""
    files = []
    for sid in sheet_ids:
        m.svg('sheet', sid)                                  # cached or rendered now
        files.append(m.cache.fn('sheet_%d.svg' % sid))
    return svgs_to_pdf(files, out_pdf)


def main():
    import argparse
    ap = argparse.ArgumentParser(prog='rvt-sheets pdf'); ap.add_argument('file'); ap.add_argument('out'); ap.add_argument('sheets', nargs='*')
    a = ap.parse_args()
    from .drawings import Model
    m = Model(os.path.abspath(a.file), allow_stale=True)
    if m._summary is None:
        m.decoder(); m._summary = m._make_summary()
    ids = [s['id'] for s in m._summary['sheets'] if not a.sheets or str(s['number']) in a.sheets]
    if not ids: sys.exit('no sheets' + (' matching %s' % a.sheets if a.sheets else ' in this file'))
    model_pdf(m, ids, os.path.abspath(a.out))
    print('wrote %s (%d sheet%s)' % (a.out, len(ids), 's' if len(ids) > 1 else ''))


if __name__ == '__main__': main()
