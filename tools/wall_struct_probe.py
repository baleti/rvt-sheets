"""wall_struct_probe.py FILE VIEWID : walls: structural usage / significance vs Revit's list in a (Structural discipline) view"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; vid = int(sys.argv[2]); o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc); I = vis.info.info; f = dec.f
G = set(o['viewelems'][vid]); pred = vis.elements(vid); v = doc['views'][vid]; print(v['name'], 'disc', v['discipline'])
c = collections.Counter()
for i in pred:
    if I[i]['cls'] == 'SWall':
        fl = f.rec(i)['fields']; c[(fl.get('m_wallStructuralUsage'), fl.get('m_isStructuralSignificant'), i in G)] += 1
print('(usage, significant, in Revit list):', sorted(c.items(), key=str))
