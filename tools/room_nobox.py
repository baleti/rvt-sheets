"""room_nobox.py FILE : rooms without a bbox: in how many views Revit lists them (gt) vs we do, with their level / phase (run on host1 for big files)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
rooms = [i for i, e in vis.info.info.items() if e['cls'] == 'RoomElem' and vis.info.bbox(i) is None]
print('rooms without bbox', len(rooms))
for r in rooms[:12]:
    fl = dec.f.rec(r)['fields']
    gtv = [vid for vid, ids in o['viewelems'].items() if r in ids]
    print(r, {k: vis.info.info[r].get(k) for k in ('level', 'created', 'owner')}, 'phase', fl.get('m_phaseId'), 'area', fl.get('m_area'), 'upper', fl.get('m_upperLevelId'), 'lvl', fl.get('m_levelId'),
          'listed in', len(gtv), [(doc['views'][v]['name'], doc['views'][v].get('phase')) for v in gtv[:4] if v in doc['views']])

    lv = dec.f.eid(fl.get('m_levelId'))
    for vid, w in doc['views'].items():
        if w.get('kind') == 'plan' and not w.get('template') and ((w.get('range') or {}).get('levels') or [None])[0] == lv:
            print('    plan', vid, w['name'][:24], 'LISTED' if r in o['viewelems'].get(vid, ()) else '-', 'vt', (w.get('range') or {}).get('plan_view_type'), 'crop', (w.get('crop') or {}).get('crop_active'), 'sc', w.get('scale'), 'disc', w.get('discipline'), 'cls', w.get('class'))
