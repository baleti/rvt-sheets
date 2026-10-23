"""datum_parts.py FILE VIEWID: for each Grid / Level listed in the view: prim part counts (line / head / text), type id and head symbol, so datums drawn without bubbles stand out"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); vid = int(sys.argv[2]); dr = vd.draw(vid)
I = vd.vis.info.info; parts = collections.defaultdict(collections.Counter)
for p in dr['prims']:
    if p.get('elem') is not None and I.get(p['elem'], {}).get('cls') in ('Grid', 'Level'): parts[p['elem']][(p['t'], p.get('part'))] += 1
for e in vd.vis.elements(vid):
    if I[e]['cls'] in ('Grid', 'Level'):
        fl = d.f.rec(e)['fields']
        print(e, I[e]['cls'], repr(fl.get('m_text')), 'type', d.f.eid(fl.get('m_attrId')), dict(parts.get(e, {})))
