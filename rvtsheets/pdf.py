"""PDF export of sheets: the cached sheet SVGs (paper size in mm) -> one PDF page each through rsvg-convert (cairo, vector).
CLI:  rvt-sheets pdf FILE.rvt OUT.pdf [SHEET_NUMBER...]   (all sheets by default, in sheet-number order; missing drawings are rendered)
The server serves GET /api/{mid}/sheet/{id}.pdf and /api/{mid}/sheets.pdf from the same function."""
import os, sys, shutil, subprocess, tempfile


def svgs_to_pdf(svg_files, out_pdf):
    """several SVG files -> one multi-page PDF (each page at the SVG's own width/height)"""
    if not shutil.which('rsvg-convert'): raise RuntimeError('rsvg-convert not installed')
    tmp = out_pdf + '.%d.tmp' % os.getpid()
    subprocess.run(['rsvg-convert', '-f', 'pdf', '-o', tmp] + list(svg_files), check=True, capture_output=True, timeout=600)
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
