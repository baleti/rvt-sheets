"""p14_probe.py FILE VID : each filter of the view: visibility / enabled / overrides, its definition (name, categories, rules) from the filter element record"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); v = doc['views'][int(sys.argv[2])]
for f in vd.vis.effective(v)['filters']:
    r = d.f.rec(f['filter']); print('P', f['filter'], 'vis', f['visible'], 'en', f['enabled'], f['overrides'], r['class'] if r else None)
    if r:
        for k, x in r['fields'].items():
            if k.startswith('m_pParam') or k in ('m_docAccess', 'm_cellList', 'm_geomSteps', 'm_pGeomTable', 'm_constrInfo', 'm_id') or 'Id' in k: continue
            print('P   ', k, str(x)[:600])
