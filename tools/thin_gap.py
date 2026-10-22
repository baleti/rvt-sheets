"""thin_gap.py OURS.svg REVIT.pdf [MAXW=0.1] : Revit's strokes up to MAXW mm that our SVG does not cover (after registering both by FFT correlation of all ink at 2 px/mm), clustered with bbox in Revit page mm.
Uses rsvg-convert for our SVG; Revit strokes are rasterised from the PDF vector data (pymupdf get_drawings)."""
import sys, subprocess, os, tempfile
import numpy as np, pymupdf
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, label, find_objects
PX = 2.0; k = 25.4 / 72
svg, pdf = sys.argv[1], sys.argv[2]; maxw = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
page = pymupdf.open(pdf)[0]; W, H = int(page.rect.width * k * PX), int(page.rect.height * k * PX)
def revit_mask(wmax=None):
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    for dr in page.get_drawings():
        w = dr.get('width')
        if dr.get('type') not in ('s', 'fs') or w is None: continue
        if wmax is not None and w * k > wmax + 1e-3: continue
        for it in dr['items']:
            if it[0] == 'l': d.line([(it[1].x * k * PX, it[1].y * k * PX), (it[2].x * k * PX, it[2].y * k * PX)], fill=255, width=1)
    return np.array(im) > 0
tmp = tempfile.mkdtemp(); png = os.path.join(tmp, 'o.png')
import re
s = open(svg).read(); m = re.search(r'width="([\d.]+)mm" height="([\d.]+)mm"', s); ow, oh = float(m.group(1)), float(m.group(2))
subprocess.run(['rsvg-convert', '-w', str(int(ow * PX)), '-b', 'white', '-o', png, svg], check=True)
o = np.array(Image.open(png).convert('L')) < 200
R = revit_mask(); Rt = revit_mask(maxw)
# register: place ours on the Revit canvas by correlation of dilated ink
def pad(a): out = np.zeros((H, W), bool); h, w = min(a.shape[0], H), min(a.shape[1], W); out[:h, :w] = a[:h, :w]; return out
A = pad(o).astype(np.float32); B = R.astype(np.float32)
f = np.fft.rfft2(B) * np.conj(np.fft.rfft2(A)); c = np.fft.irfft2(f, s=B.shape)
dy, dx = np.unravel_index(np.argmax(c), c.shape); dy = dy - H if dy > H // 2 else dy; dx = dx - W if dx > W // 2 else dx
A2 = np.roll(np.roll(A > 0, dy, 0), dx, 1)
print('ours %dx%d mm  shift mm (%.1f, %.1f)  ink px revit %d ours %d' % (ow, oh, dx / PX, dy / PX, R.sum(), A2.sum()))
cov = binary_dilation(A2, iterations=3)
miss = Rt & ~cov
lab, n = label(binary_dilation(miss, iterations=6)); sl = find_objects(lab)
rows = []
for i, s_ in enumerate(sl):
    cnt = int((miss[s_] & (lab[s_] == i + 1)).sum())
    if cnt > 30: rows.append((cnt / PX, [round(s_[1].start / PX), round(s_[0].start / PX), round(s_[1].stop / PX), round(s_[0].stop / PX)]))
rows.sort(reverse=True)
print('Revit thin ink missing in ours: %.0f mm in %d clusters (thin total %.0f mm)' % (miss.sum() / PX, len(rows), Rt.sum() / PX))
for L, b in rows[:15]: print('  %.0f mm at page-mm bbox %s' % (L, b))
