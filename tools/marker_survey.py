"""marker_survey.py FILE : per plan view, are InteriorElevArrow markers in Revit's list vs the plan's level elevation / cut / range and the arrow's bounded-space z extent"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rvtsheets.decode import Decoder
from rvtsheets import oracle
from rvtsheets.reader import ob
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); f = dec.f
lev = {}
for r in f.recs('Level'):
    s = ob(r['fields'].get('m_pSurface')) or {}
    if s.get('m_origin'): lev[r['id']] = s['m_origin'][2]
arrows = []
for r in f.recs('InteriorElevArrow'):
    bs = ob(r['fields'].get('m_boundedSpace')) or {}
    if bs.get('m_basis'):
        org = np.asarray(bs['m_orig'], float); B = np.asarray(bs['m_basis'], float); bo = bs['m_boundOffset']
        zs = [float((org + B[0] * x + B[1] * y)[2]) for x in bo[0] for y in bo[1]]
        arrows.append((r['id'], min(zs), max(zs)))
print('arrows (id, zmin, zmax):', [(a, round(lo, 2), round(hi, 2)) for a, lo, hi in arrows])
for vid, ids in sorted(o['viewelems'].items()):
    v = doc['views'].get(vid)
    if not v or v['kind'] != 'plan' or v.get('template'): continue
    rg = v.get('range') or {}; G = set(ids)
    print(vid, v['name'][:26].ljust(26), 'level', round(lev.get(v['level'], -999), 2), 'cut', round(rg.get('cut') or 0, 2), 'type', rg.get('plan_view_type'), 'ndf', len(v.get('draw_filters') or []), 'listed', len([a for a, _, _ in arrows if a in G]), 'of', len(arrows))
