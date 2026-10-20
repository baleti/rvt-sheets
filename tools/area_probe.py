"""area_probe.py FILE [AREA_ID]: area elements (RoomElem with m_areaSchemeId): scheme, point, boundary lines of the scheme (offset to the wall finish), polygon area vs Revit's printed value"""
import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import annot
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); f = dec.f
d = types.SimpleNamespace(f=f, vis=vis)
for e, i in vis.info.info.items():
    if i['cls'] != 'RoomElem': continue
    r = f.rec(e)
    if not annot.f_isarea(types.SimpleNamespace(f=f), r): continue
    if len(sys.argv) > 2 and int(sys.argv[2]) != e: continue
    fl = r['fields']
    print(e, 'scheme', f.eid(fl.get('m_areaSchemeId')), 'point', fl.get('m_point'), 'level', f.eid(fl.get('m_assocLevelId')), 'poly area', annot._area_of_scheme_region(d, r))
    print('  keys', [k for k in fl if any(s in k for s in ('oundar', 'egment', 'ircuit', 'rea', 'oint'))])
