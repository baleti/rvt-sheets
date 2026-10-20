"""dim_probe.py FILE VIEWID [DIMID]: linear dimensions of a view: stored segment values, reference points (view-independent world feet), referenced element class / geometry tag,
and for straight-wall references the signed offsets of the wall's two side faces along the dimension direction vs the stored point (a moved wall shows as a drift)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.reader import ob, path, wref, INVALID
from rvtsheets import units
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); f = dec.f
vid = int(sys.argv[2]); only = int(sys.argv[3]) if len(sys.argv) > 3 else None
lst = vis.elements(vid)
from rvtsheets import oracle
try: gtl = set(oracle.load(oracle.find(sys.argv[1]))['viewelems'].get(vid, []))
except Exception: gtl = None
import re, glob
rev = None
try:
    import pymupdf
    gt = sorted(d for d in glob.glob(os.path.expanduser('~/rvt-research/gt_views/*')) if d.endswith(os.path.splitext(os.path.basename(sys.argv[1]))[0]) and os.path.isdir(d))[-1]
    pg = pymupdf.open(os.path.join(gt, '%d.pdf' % vid))[0]
    rev = {w for b in pg.get_text('dict')['blocks'] for l in b.get('lines', []) for sp in l['spans'] for w in re.sub(r'\s+', ' ', sp['text']).strip().split(' ') if w}
except Exception: rev = None
def wall_faces(e, d):
    """(centre offset, half width) of a straight wall along direction d (world xy), or None"""
    r = f.rec(e)
    if not r or r['class'] != 'SWall': return None
    fl = r['fields']; cr = ob(path(ob(fl.get('m_pCurveDriver')) or {}, 'm_pCrv')) or {}
    if not cr.get('m_origin') or cr.get('m_radius'): return None
    t = f.rec(f.eid(fl.get('m_WallAttributesId'))); cs = ob((t or {'fields': {}})['fields'].get('m_pCompoundStructure')) or {}
    w = sum((ob(x).get('m_layerWidth') or 0) for x in cs.get('m_layers') or [])
    o = np.asarray(cr['m_origin'], float)[:2]; u = np.asarray(cr['m_dirVec'], float)[:2]
    nrm = np.array([-u[1], u[0]]); off = float(fl.get('m_locLineOffset') or 0.0)
    return float((o + nrm * off) @ d), w / 2, nrm @ d, fl.get('m_isFlipped')
for e in lst:
    i = vis.info.info[e]
    if i['cls'] != 'LinearDimString' or (only and e != only): continue
    fl = f.rec(e)['fields']; dl = ob(fl.get('m_pDimLine')) or {}
    if not dl.get('m_origin'): continue
    d = np.asarray(dl['m_dirVec'], float)[:2]; d /= np.linalg.norm(d) or 1
    rp = [np.asarray(p, float) for p in fl.get('m_refPnts') or []]
    segs = fl.get('m_ArrSegInfo') or []
    vals = [((sg.get('m_values') or [{}])[0] or {}).get('m_value') for sg in segs]
    inpdf = None if rev is None else [all(w in rev for w in t.split(' ')) for t in [units.fmt_length(v, {'m_bUseDefault': 1}, units.length_format(f)) for v in vals if v is not None]]
    print('DIM', e, 'inPDF', inpdf, 'stored', [units.fmt_length(v, {'m_bUseDefault': 1}, units.length_format(f)) if v is not None else None for v in vals], 'raw', [round(v, 4) for v in vals if v is not None])
    for k, w in enumerate(fl.get('m_witnessRefs') or []):
        g = wref(w).get('m_geomRef') or {}; el = f.eid(g.get('m_elemId')); cls = (f.rec(el) or {}).get('class') if el not in (None, INVALID, -1) else None
        pt = rp[k] if k < len(rp) else None
        wf = wall_faces(el, d) if cls == 'SWall' else None
        print('   ref', k, 'elem', el, cls, 'inGT', None if gtl is None else el in gtl, 'inOurs', el in lst, 'tag', g.get('m_geomTag'), 'pt.d', None if pt is None else round(float(pt[:2] @ d), 4),
              '' if not wf else 'wall centre.d %.4f half %.4f n.d %.2f flipped %s -> faces %.4f / %.4f' % (wf[0], wf[1], wf[2], wf[3], wf[0] - wf[1], wf[0] + wf[1]))
