"""noprim_elems.py FILE VIEWID : elements the visibility stage lists for a view that ViewDrawer draws no prim for (class, category, bbox centre ft)."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); vid = int(sys.argv[2])
dr = ViewDrawer(dec, doc, ).draw(vid) if False else None
vd = ViewDrawer(dec, doc); dr = vd.draw(vid)
drawn = {p.get('elem') for p in dr['prims']}
ids = vis.elements(vid)
miss = [i for i in ids if i not in drawn]
c = collections.Counter((vis.info.info[i].get('cls')) for i in miss if i in vis.info.info)
print('listed', len(ids), 'no prim', len(miss), c.most_common(15))
cat = collections.Counter(vis.info.info[i].get('cat') for i in miss if i in vis.info.info and vis.info.info[i].get('cls') == 'FamilyInstance')
print('FamilyInstance categories without prims', cat)
for i in miss:
    e = vis.info.info.get(i, {})
    if e.get('cls') == 'FamilyInstance' and e.get('cat') == -2001160:
        print('planting', i, 'type', e.get('type'), 'fam', e.get('fam'), 'rphase', e.get('rphase'), 'dopt', e.get('dopt'), 'vflags', e.get('vflags'))
