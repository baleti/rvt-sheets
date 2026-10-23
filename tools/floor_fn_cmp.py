"""floor_fn_cmp.py FILE.rvt : FN elements excluded as outside_view_volume (class Floor-like) vs same-class elements in the same view that we also exclude and Revit does not list:
attributes side by side (level, vflags, type, workset, phase, bbox z, view range)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc); f = dec.f
for vid, G in o['viewelems'].items():
    v = doc['views'].get(vid)
    if not v or v['kind'] != 'plan': continue
    out, why = vis.elements(vid, explain=True) if True else (None, None)
    fnl = [e for e in G if e not in out and why.get(e) == 'outside_view_volume' and vis.info.info[e]['cls'] in ('Floor', 'FloorElem', 'Slab')]
    if not fnl: continue
    cls = {vis.info.info[e]['cls'] for e in fnl}
    unl = [e for e, w in why.items() if w == 'outside_view_volume' and e not in G and vis.info.info[e]['cls'] in cls]
    print('VIEW', vid, v['name'], 'range', v.get('range'), 'FN', len(fnl), 'unlisted same class', len(unl))
    def row(e):
        i = vis.info.info[e]; fl = f.rec(e)['fields']
        return (e, i['cls'], i['cat'], i.get('level'), i['vflags'], f.eid(fl.get('m_symbolId') or fl.get('m_famId')), i.get('phase'), [round(x, 2) for x in (i.get('bbox') or [])][:6] if not hasattr(i.get('bbox'), 'tolist') else i['bbox'].round(2).tolist())
    for e in fnl: print('  FN ', row(e))
    for e in unl[:12]: print('  not', row(e))
