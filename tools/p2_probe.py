"""p2_probe.py FILE VID... : is the Structural Beam Systems category (-2001327) hidden per view, and which framing/joist elements does the view list"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc)
for vid in map(int, sys.argv[2:]):
    v = doc['views'][vid]; hc = vd.vis.hidden_categories(vd.vis.effective(v))[0]
    print('P', vid, v.get('name'), 'beamsys hidden', -2001327 in hc, 'framing hidden', -2001320 in hc, 'joistsys listed', sum(1 for e in vd.vis.elements(vid) if vd.vis.info.info[e]['cls'] == 'JoistSystem'), 'template', v.get('template'))
    r = v['range']; print('P  range', {k: (round(x, 2) if isinstance(x, float) else x) for k, x in r.items() if k in ('cut', 'top', 'bottom', 'depth')})
    for e in vd.vis.elements(vid):
        if vd.vis.info.info[e]['cls'] == 'JoistSystem':
            ms = [m for m in vd.vis.elements(vid) if (d.f.rec(m) or {}).get('class') == 'FamilyInstance' and d.f.eid((d.f.rec(m)['fields'].get('m_hostId'))) == e]
            bbs = [vd.vis.info.bbox(m) for m in ms]; bbs = [b for b in bbs if b is not None]
            if bbs: print('P  js', e, len(ms), 'z', round(min(float(b[0][2]) for b in bbs), 2), round(max(float(b[1][2]) for b in bbs), 2))
    print('P  detail', vd.vis.effective(v).get('detail_level'), 'scale', v.get('scale'), 'disc', v.get('discipline'))
