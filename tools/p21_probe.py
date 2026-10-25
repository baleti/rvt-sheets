"""p21_probe.py FILE VID N : first N Rebar element ids listed in the view that our draw gives prims (with discipline / display)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); vid = int(sys.argv[2]); n = int(sys.argv[3])
dr = vd.draw(vid); prims = dr['prims'] if isinstance(dr, dict) else dr.prims
drawn = {p.get('elem') for p in prims}
els = [e for e in vd.vis.elements(vid) if vd.vis.info.info[e]['cls'] in ('Rebar', 'RebarInSystem')]
v = doc['views'][vid]
print('P', vid, v.get('name'), 'disc', v.get('discipline'), 'surfaces', ((v.get('display') or {}).get('m_model') or {}).get('m_surfaces'), 'rebar listed', len(els), 'drawn', sum(1 for e in els if e in drawn))
print('P ids drawn', [e for e in els if e in drawn][:n], 'undrawn', [e for e in els if e not in drawn][:n])
