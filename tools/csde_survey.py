"""csde_survey.py FILE : per view, is the CoordinateSystemDisplayElem in Revit's list, and why does our model (not) list it"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc); I = vis.info.info
cs = [i for i in I if I[i]['cls'] == 'CoordinateSystemDisplayElem']
print('elements', cs, [(I[i]['cat'], vis.info.bbox(i) is not None and vis.info.bbox(i).round(1).tolist()) for i in cs])
for vid, ids in sorted(o['viewelems'].items()):
    v = doc['views'].get(vid)
    if not v or v['kind'] in ('schedule', 'sheet'): continue
    pred, why = vis.elements(vid, explain=True)
    hid = vis.hidden_categories(vis.effective(v))[0]
    print(vid, v['kind'].ljust(8), v['name'][:24].ljust(24), 'revit', any(i in ids for i in cs), 'ours', any(i in pred for i in cs), [why.get(i) for i in cs], 'crop', (v.get('crop') or {}).get('crop_active'), 'cat hidden', [I[i]['cat'] in hid for i in cs], 'scale', v.get('scale'))
