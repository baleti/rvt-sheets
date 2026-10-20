"""proplines_check.py FILE GT_DIR: per plan view, are property line segments listed by our visibility rule vs Revit's DXF (C-PROP-LINE present)? Prints MISMATCH lines; exit 1 if any."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); d = sys.argv[2]
pl = [e for e, i in vis.info.info.items() if i['cls'] == 'PropertyLineSegment']
bad = n = 0
if pl:
    for vid, w in doc['views'].items():
        p = os.path.join(d, '%d.dxf' % vid)
        if w.get('kind') != 'plan' or not os.path.exists(p): continue
        has = 'C-PROP-LINE' in open(p, errors='replace').read(); lst = vis.elements(vid); ours = any(k in lst for k in pl); n += 1
        if has != ours: bad += 1; print('MISMATCH', vid, w['name'], 'DXF', has, 'ours', ours)
print('plans checked', n, 'mismatches', bad)
sys.exit(1 if bad else 0)
