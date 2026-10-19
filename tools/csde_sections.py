"""csde_sections.py FILE : sections / elevations: is the coordinate-system element in Revit's list, and where is the model origin in the crop frame"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); d = Decoder(fn); doc = d.doc(); vis = Visibility(d, doc)
cs = [i for i, x in vis.info.info.items() if x['cls'] == 'CoordinateSystemDisplayElem'][0]
for vid, ids in sorted(o['viewelems'].items()):
    v = doc['views'].get(vid)
    if not v or v['kind'] != 'section': continue
    P = set(vis.elements(vid)); ve = vis.effective(v); c = ve['crop']
    if not c.get('basis'): continue
    co = np.array(c['origin']); B = np.array(c['basis']); b = c['bounds']; l = (np.zeros(3) - co) @ B.T
    print(vid, v['name'][:22].ljust(22), 'GT', cs in ids, 'ours', cs in P, 'origin local', l.round(1), 'x', np.round(b[0], 1), 'y', np.round(b[1], 1), 'z', np.round(b[2], 1), 'cls', v.get('class'), 'cutter', bool(v.get('cutters')))
