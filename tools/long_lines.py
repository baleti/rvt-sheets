"""long_lines.py FILE VIEWID [MINFT]: drawn straight lines longer than MINFT (default 30 ft) by element class / category / id (stray long lines, e.g. reference planes, markers)"""
import sys, os, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); vid = int(sys.argv[2]); mn = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
dr = vd.draw(vid); I = vd.vis.info.info; c = collections.defaultdict(list)
for p in dr['prims']:
    segs = p.get('segs') or ([p['pts']] if p.get('pts') else [])
    for s in segs:
        a = np.asarray(s, float)[:, :2]
        if len(a) >= 2 and np.linalg.norm(a[-1] - a[0]) > mn and len(a) <= 3: c[(I.get(p.get('elem'), {}).get('cls'), (doc['categories'].get(I.get(p.get('elem'), {}).get('cat')) or {}).get('name'), p.get('layer'), p.get('part'))].append(p.get('elem'))
for k, v in sorted(c.items(), key=lambda kv: -len(kv[1])): print(k, len(v), sorted(set(v))[:6])
