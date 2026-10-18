"""room_probe.py FILE VIEWID : rooms in Revit's list vs our room_not_at_cut verdict (bbox z vs cut)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; vid = int(sys.argv[2]); o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc); I = vis.info.info
v = doc['views'][vid]; rg = v['range']; print('cut', rg['cut'], 'bottom', rg['bottom'], 'top', rg['top'], 'level', v['level'])
pred, why = vis.elements(vid, explain=True); G = set(o['viewelems'][vid])
for i in I:
    if I[i]['cls'] == 'RoomElem':
        bb = vis.info.bbox(i); fl = dec.f.rec(i)['fields']
        print(i, 'revit' if i in G else '-', 'ours', i in pred, why.get(i), 'bbz', None if bb is None else bb[:, 2].round(2).tolist(), 'lvl', dec.f.eid(fl.get('m_levelId')), 'upper', dec.f.eid(fl.get('m_upperLevelId')), 'limitoff', fl.get('m_limitOffset'), fl.get('m_baseOffset'))
