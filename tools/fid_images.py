"""fid_images.py FILE.rvt EXPORT_DIR OUT_DIR [--max N] -> per exported view/sheet (EXPORT_DIR/index.tsv from oracle/viewexport.cs):
our SVG, rasterised at the PNG's size, compared with Revit's PNG (SSIM, ink precision/recall at 3 px, chamfer px; registered by ink bbox
because FitToPage margins are unknown) and, for views with a DXF, linework precision/recall in paper mm (compare_dxf).
Writes OUT_DIR/results.jsonl and OUT_DIR/table.md; diff images OUT_DIR/<id>_diff.png (red = Revit only, blue = ours only)."""
import sys, os, json, subprocess, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.viewsvg import view_svg
from rvtsheets.compose import sheet_svg, crop_rect_uv
import compare_img as CI

fn, exp, out = sys.argv[1], sys.argv[2], sys.argv[3]
mx = int(sys.argv[sys.argv.index('--max') + 1]) if '--max' in sys.argv else 999
os.makedirs(out, exist_ok=True)
dec = Decoder(fn); doc = dec.doc(); vd = ViewDrawer(dec, doc)
rows = []
for line in open(os.path.join(exp, 'index.tsv'), encoding='utf-8'):
    c = line.rstrip('\n').split('\t')
    if c[0] != 'VIEW': continue
    vid = int(c[1]); files = c[7].split(',') if len(c) > 7 and c[7] else []
    rows.append((vid, c[2], c[4], files))
res = []
for vid, cls, name, files in rows[:mx]:
    t = time.time(); r = {'id': vid, 'class': cls, 'name': name}
    try:
        if cls == 'ViewSheet': svg = sheet_svg(dec, vid, doc, vd, log=lambda *a: None)
        else:
            v = doc['views'].get(vid)
            if not v or v['kind'] not in ('plan', 'section', 'drafting', 'legend', '3d'): r['skip'] = 'kind %s' % (v or {}).get('kind'); res.append(r); continue
            svg = view_svg(vd.draw(vid), v.get('scale') or 100, margin_mm=0, crop=crop_rect_uv(v))
        sfn = os.path.join(out, '%d.svg' % vid); open(sfn, 'w').write(svg)
        import shutil
        if vid and ('%d.png' % vid) in files and shutil.which('rsvg-convert'):
            rv = CI.load(os.path.join(exp, '%d.png' % vid)); ou = CI.load(sfn, rv.shape[1])
            m, ou2 = CI.compare(ou, rv, register=True)
            r.update({k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()})
            CI.diff_image(ou2, rv, os.path.join(out, '%d_diff.png' % vid))
        if ('%d.dxf' % vid) in files and cls != 'ViewSheet':
            p = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compare_dxf.py'), fn, str(vid), os.path.join(exp, '%d.dxf' % vid), '--register'], capture_output=True, text=True, timeout=600)
            try:
                d = json.loads(p.stdout); r.update(dxf_precision=round(d['precision'], 4), dxf_recall=round(d['recall'], 4), dxf_layers=d['recall_by_revit_layer'])
            except Exception: r['dxf_error'] = (p.stderr or p.stdout)[-300:]
    except Exception as ex:
        r['error'] = repr(ex)[:300]
    r['seconds'] = round(time.time() - t, 1); res.append(r)
    print(json.dumps({k: v for k, v in r.items() if k != 'dxf_layers'}), flush=True)
with open(os.path.join(out, 'results.jsonl'), 'w') as fo:
    for r in res: fo.write(json.dumps(r) + '\n')
with open(os.path.join(out, 'table.md'), 'w') as fo:
    fo.write('| id | class | name | SSIM | ink P | ink R | chamfer px | DXF P | DXF R |\n|---|---|---|---|---|---|---|---|---|\n')
    for r in res:
        fo.write('| %s | %s | %s | %s | %s | %s | %s | %s | %s |\n' % (r['id'], r['class'], r['name'][:40], r.get('ssim', ''), r.get('ink_precision', ''), r.get('ink_recall', ''),
                 r.get('chamfer_px', ''), r.get('dxf_precision', ''), r.get('dxf_recall', '') if 'skip' not in r else r['skip']))
