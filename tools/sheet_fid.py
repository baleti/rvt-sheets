"""sheet_fid.py OUT.tsv FILE.rvt GTDIR [...] : raster fidelity (SSIM, ink P / R, chamfer) of every cached sheet SVG against Revit's sheet PNG in GTDIR (pairs of FILE GTDIR); run on host3 (needs rsvg-convert, small)"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.environ.get('RVT_SHEETS_TREE', os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import compare_img as CI
from rvtsheets.cache import Cache
out = sys.argv[1]; args = sys.argv[2:]
with open(out, 'w') as o:
    for fn, gt in zip(args[::2], args[1::2]):
        c = Cache(fn)
        for svg in sorted(glob.glob(os.path.join(c.dir, 'sheet_*.svg'))):
            sid = os.path.basename(svg)[6:-4]; png = os.path.join(gt, sid + '.png')
            if not os.path.exists(png): continue
            try:
                rv = CI.load(png); ou = CI.load(svg, rv.shape[1]); m, _ = CI.compare(ou, rv, register=True)
                o.write('%s\t%s\t%.4f\t%.4f\t%.4f\t%.1f\n' % (os.path.basename(fn)[:30], sid, m['ssim'], m['ink_precision'], m['ink_recall'], m['chamfer_px'])); o.flush()
            except Exception as e: o.write('%s\t%s\terror %s\n' % (os.path.basename(fn)[:30], sid, e))
