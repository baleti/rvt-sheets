"""floor_level_rule.py FILE.rvt : for plan views, Floors we exclude as outside_view_volume: Revit-listed vs not, split by 'associated level == a level of the view range'"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc); f = dec.f
c = collections.Counter(); ex = []
for vid, G in o['viewelems'].items():
    v = doc['views'].get(vid)
    if not v or v['kind'] != 'plan' or not v.get('range'): continue
    out, why = vis.elements(vid, explain=True)
    lv = set(v['range']['levels'])
    for e, w in why.items():
        if w != 'outside_view_volume' or vis.info.info[e]['cls'] != 'Floor': continue
        al = f.eid(f.rec(e)['fields'].get('m_assocLevelId'))
        key = (al in lv, e in G)
        c[key] += 1
        if key[0] and len(ex) < 12: ex.append((vid, e, al, e in G))
print('(assoc level in view range levels, revit lists):', dict(c)); print(ex)
