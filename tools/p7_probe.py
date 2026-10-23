"""p7_probe.py FILE VID : the view's filters (name, categories, rules, visibility) and the elements of the given classes they match"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); v = doc['views'][int(sys.argv[2])]
ev = vd.vis.effective(v)
for k, x in ev.items():
    if 'filter' in k.lower(): print('P', k, str(x)[:1500])
