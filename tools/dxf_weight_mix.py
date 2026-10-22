"""dxf_weight_mix.py FILE VIEWID REVIT.dxf : share of ink per line weight (mm) in Revit's DXF (entity group 370 / BYLAYER layer table weights, LINE / LWPOLYLINE / ARC) vs ours (dash-aware) for 2020 files without a PDF export"""
import sys, os, math, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
L = open(sys.argv[3], errors='ignore').read().split('\n'); pairs = [(L[i].strip(), L[i + 1].strip()) for i in range(0, len(L) - 1, 2)]
ents = []; cur = None; layers = {}; sec = None
for c, v in pairs:
    if c == '0':
        if cur: ents.append(cur)
        cur = {'type': v}
    elif cur is not None: cur.setdefault(c, []).append(v)
if cur: ents.append(cur)
for e in ents:
    if e['type'] == 'LAYER' and '2' in e: layers[e['2'][0]] = int(e.get('370', ['-3'])[0])
rev = collections.Counter(); tot = 0
for e in ents:
    if e['type'] not in ('LINE', 'LWPOLYLINE'): continue
    try:
        if e['type'] == 'LINE': l = math.hypot(float(e['11'][0]) - float(e['10'][0]), float(e['21'][0]) - float(e['20'][0]))
        else:
            xs = [float(x) for x in e.get('10', [])]; ys = [float(y) for y in e.get('20', [])]; l = sum(math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(len(xs) - 1))
    except Exception: continue
    w = int(e['370'][0]) if '370' in e else layers.get(e.get('8', ['0'])[0], -3)
    rev[w if w >= 0 else 'bylayer?'] += l; tot += l
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2]); vd = ViewDrawer(dec, doc); dr = vd.draw(vid); sc = doc['views'][vid].get('scale') or 96
ours = collections.Counter(); ot = 0
for p in dr['prims']:
    st = p.get('style') or {}; w = round(st.get('w') or 0, 2)
    if p.get('t') == 'line' and p.get('pts') is not None and len(p['pts']) > 1: pts = np.asarray(p['pts'], float); l = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    elif p.get('t') in ('segs', 'cut') and p.get('segs'): l = sum(float(np.linalg.norm(np.asarray(b, float) - np.asarray(a, float))) for a, b in p['segs'])
    else: continue
    l *= 304.8 / sc; d = st.get('dash'); l *= (sum(d[0::2]) / sum(d)) if d else 1.0
    ours[w] += l; ot += l
print('REVIT DXF share by weight (1/100 mm):', {k: round(v / tot, 3) for k, v in sorted(rev.items(), key=lambda kv: str(kv[0]))})
print('OURS share by width (mm):', {k: round(v / ot, 3) for k, v in sorted(ours.items())})
