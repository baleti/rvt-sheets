"""csde_3d.py FILE : 3D views: coordinate-system element in Revit's list vs ours, with section box state / crop / perspective"""
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
    if not v or v['kind'] != '3d': continue
    P = set(vis.elements(vid)); sb = v.get('section_box') or {}
    loc = None
    if sb.get('origin') is not None:
        loc = ((np.zeros(3) - np.asarray(sb['origin'], float)) @ np.asarray(sb['basis'], float).T).round(1).tolist()
    print(vid, v['name'][:24].ljust(24), 'GT', cs in ids, 'ours', cs in P, 'box on', sb.get('on'), 'origin local', loc, 'bounds', None if not sb else [[round(x, 1) for x in b] for b in sb['bounds']], 'persp', v.get('perspective'), 'tpl', v.get('template_id'))
