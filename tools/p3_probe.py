"""p3_probe.py FILE : per view kind / discipline / detail level / name (which views are fine + coordination)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc)
for vid, v in doc['views'].items():
    if v.get('kind') not in ('plan',): continue
    print('P', vid, v.get('name'), v.get('kind'), 'disc', v.get('discipline'), 'detail', vd.vis.effective(v).get('detail_level'), 'scale', v.get('scale'))
