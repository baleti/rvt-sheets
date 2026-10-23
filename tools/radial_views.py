"""radial_views.py FILE: views whose element list (visibility.elements) contains RadialDim records, with the ids"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
d = Decoder(sys.argv[1]); doc = d.doc(); vis = Visibility(d, doc); I = vis.info.info
for vid, v in doc['views'].items():
    try: l = vis.elements(vid)
    except Exception: continue
    rd = [e for e in l if I.get(e, {}).get('cls') == 'RadialDim']
    if rd: print(vid, v.get('name'), v.get('kind'), len(rd), rd[:5], flush=True)
