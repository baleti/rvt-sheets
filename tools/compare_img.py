"""compare_img.py OURS.svg|png REVIT.png [--out DIFF.png] -> SSIM (grey, gaussian window), ink precision/recall at tolerance,
symmetric chamfer distance of ink pixels (mean, px and mm), registered by scale+translation search on ink bounding boxes.
Both images are binarised for the edge metrics (ink = luminance < 200)."""
import sys, os, subprocess, tempfile, json
import numpy as np
from PIL import Image
from scipy import ndimage

def load(fn, width=None):
    if fn.endswith('.svg'):
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False).name
        subprocess.run(['rsvg-convert', '-w', str(width or 3000), '-b', 'white', fn, '-o', tmp], check=True)
        fn = tmp
    im = Image.open(fn).convert('L')
    return np.asarray(im, float) / 255.0


def ssim(a, b, sigma=1.5):
    C1, C2 = 0.01 ** 2, 0.03 ** 2
    mu_a = ndimage.gaussian_filter(a, sigma); mu_b = ndimage.gaussian_filter(b, sigma)
    saa = ndimage.gaussian_filter(a * a, sigma) - mu_a ** 2; sbb = ndimage.gaussian_filter(b * b, sigma) - mu_b ** 2; sab = ndimage.gaussian_filter(a * b, sigma) - mu_a * mu_b
    m = ((2 * mu_a * mu_b + C1) * (2 * sab + C2)) / ((mu_a ** 2 + mu_b ** 2 + C1) * (saa + sbb + C2))
    return float(m.mean())


def ink(a, thr=200 / 255): return a < thr


def bbox(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs): return None
    return xs.min(), ys.min(), xs.max(), ys.max()


def compare(ours, revit, px_mm=None, tol_px=3, register=False):
    """ours / revit: grey arrays of the SAME page (same paper extents) -> metrics. register=True aligns ink bboxes (when the page mapping is unknown)"""
    if ours.shape != revit.shape:
        ours = np.asarray(Image.fromarray((ours * 255).astype(np.uint8)).resize(revit.shape[::-1], Image.BILINEAR), float) / 255
    A = ink(ours); B = ink(revit)
    if register:
        ba, bb = bbox(A), bbox(B)
        if ba and bb:
            sx = (bb[2] - bb[0]) / max(ba[2] - ba[0], 1); sy = (bb[3] - bb[1]) / max(ba[3] - ba[1], 1)
            M = np.array([[1 / sy, 0], [0, 1 / sx]]); off = np.array([ba[1] - bb[1] / sy, ba[0] - bb[0] / sx])
            ours = ndimage.affine_transform(ours, M, offset=off, order=1, cval=1.0); A = ink(ours)
    dA = ndimage.distance_transform_edt(~A); dB = ndimage.distance_transform_edt(~B)
    prec = float((dB[A] <= tol_px).mean()) if A.any() else 0.0          # our ink near Revit ink
    rec = float((dA[B] <= tol_px).mean()) if B.any() else 0.0           # Revit ink near ours
    cham = float((dB[A].mean() + dA[B].mean()) / 2) if A.any() and B.any() else float('nan')
    r = {'ssim': ssim(ours, revit), 'ink_precision': prec, 'ink_recall': rec, 'chamfer_px': cham, 'ink_ours': int(A.sum()), 'ink_revit': int(B.sum())}
    if px_mm: r['chamfer_mm'] = cham * px_mm
    return r, ours


def diff_image(ours, revit, fn):
    A = ink(ours); B = ink(revit)
    rgb = np.full(A.shape + (3,), 255, np.uint8)
    rgb[B & ~A] = [220, 40, 40]          # Revit only: red
    rgb[A & ~B] = [40, 90, 220]          # ours only: blue
    rgb[A & B] = [0, 0, 0]
    Image.fromarray(rgb).save(fn)


if __name__ == '__main__':
    a = sys.argv[1]; b = sys.argv[2]
    rv = load(b); ou = load(a, rv.shape[1])
    reg = '--register' in sys.argv
    r, ou2 = compare(ou, rv, register=reg)
    print(json.dumps(r))
    if '--out' in sys.argv: diff_image(ou2, rv, sys.argv[sys.argv.index('--out') + 1])
