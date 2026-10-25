"""view_png_cmp.py GTDIR SVGDIR : SSIM / ink P / ink R / chamfer of every SVGDIR/<id>.svg vs GTDIR/<id>.png (host3, needs rsvg-convert)"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare_img as CI
gt, d = sys.argv[1:3]
for svg in sorted(glob.glob(os.path.join(d, '*.svg'))):
    vid = os.path.basename(svg)[:-4]; png = os.path.join(gt, vid + '.png')
    try:
        rv = CI.load(png); ou = CI.load(svg, rv.shape[1]); m, _ = CI.compare(ou, rv, register=True)
        print('%s\t%.3f\t%.3f\t%.3f\t%.1f' % (vid, m['ssim'], m['ink_precision'], m['ink_recall'], m['chamfer_px']))
    except Exception as e: print(vid, 'error', e)
