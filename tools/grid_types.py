"""grid_types.py FILE VIEWID : for each Grid / Level: Type Name, listed by Revit (gt) in the view, listed by us"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.filters import FilterEval
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc); fe = FilterEval(dec, doc)
vid = int(sys.argv[2]); pred = vis.elements(vid); G = set(o['viewelems'][vid])
c = collections.Counter()
for i, e in vis.info.info.items():
    if e['cls'] in ('Grid', 'Level'):
        c[(e['cls'], fe.value(i, {'param_name': 'Type Name'}), i in G, i in pred)] += 1
for k, n in sorted(c.items(), key=str): print(k, n)
