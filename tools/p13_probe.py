"""p13_probe.py FILE VID VID... : side by side view settings that differ (effective view + record scalars)"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc)
vs = [int(x) for x in sys.argv[2:]]
E = {v: dict(vd.vis.effective(doc['views'][v])) for v in vs}
for v in vs: E[v]['_range'] = doc['views'][v].get('range'); E[v]['_crop'] = (doc['views'][v].get('crop') or {}).get('bounds'); E[v]['_name'] = doc['views'][v].get('name')
keys = sorted({k for e in E.values() for k in e})
for k in keys:
    vals = [json.dumps(E[v].get(k), default=str)[:200] for v in vs]
    if len(set(vals)) > 1: print('P', k, ' | '.join(vals))
