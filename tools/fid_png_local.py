"""fid_png_local.py EXPORT_DIR OUT_DIR -> raster comparison of OUT_DIR/<id>.svg against EXPORT_DIR/<id>.png (run on host3: needs rsvg-convert);
merges into OUT_DIR/results.jsonl and rewrites OUT_DIR/table.md"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare_img as CI
exp, out = sys.argv[1], sys.argv[2]
res = [json.loads(l) for l in open(os.path.join(out, 'results.jsonl'))]
for r in res:
    svg = os.path.join(out, '%d.svg' % r['id']); png = os.path.join(exp, '%d.png' % r['id'])
    if 'skip' in r or not os.path.exists(svg) or not os.path.exists(png): continue
    rv = CI.load(png); ou = CI.load(svg, rv.shape[1])
    m, ou2 = CI.compare(ou, rv, register=True)
    r.update({k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()})
    CI.diff_image(ou2, rv, os.path.join(out, '%d_diff.png' % r['id']))
with open(os.path.join(out, 'results.jsonl'), 'w') as fo:
    for r in res: fo.write(json.dumps(r) + '\n')
with open(os.path.join(out, 'table.md'), 'w') as fo:
    fo.write('| id | class | name | SSIM | ink P | ink R | chamfer px | DXF P | DXF R |\n|---|---|---|---|---|---|---|---|---|\n')
    for r in res:
        fo.write('| %s | %s | %s | %s | %s | %s | %s | %s | %s |\n' % (r['id'], r['class'], r['name'][:40], r.get('ssim', ''), r.get('ink_precision', ''), r.get('ink_recall', ''),
                 r.get('chamfer_px', ''), r.get('dxf_precision', ''), r.get('dxf_recall', '') if 'skip' not in r else r['skip']))
import numpy as np
for k in ('ViewSheet', 'ViewPlan', 'ViewSection', 'ViewDrafting', 'View3D'):
    xs = [r for r in res if r['class'] == k and 'ssim' in r]
    if xs: print(k, len(xs), 'SSIM %.3f inkP %.3f inkR %.3f' % tuple(np.mean([r[m] for r in xs]) for m in ('ssim', 'ink_precision', 'ink_recall')),
                 'DXF P/R %.3f/%.3f' % (np.mean([r.get('dxf_precision', np.nan) for r in xs]), np.mean([r.get('dxf_recall', np.nan) for r in xs])))
