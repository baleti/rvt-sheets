"""vp_spec.py FILE OUTDIR [WIDTH] : camera spec json of every perspective 3D view that a sheet shows (for the viewer's tools/shot3d.py --spec):
{eye [x,y,z] ft, dir = stored view direction (points to the eye), tl/tr/tt/tb = crop tangents b[0][1]/pd, b[0][0]/pd, b[1][0]/pd, b[1][1]/pd, size [W, H], view, name, sheet viewport offset/scale}"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
fn, out = sys.argv[1], sys.argv[2]; W = int(sys.argv[3]) if len(sys.argv) > 3 else 1800
doc = Decoder(fn).doc(); os.makedirs(out, exist_ok=True)
for sid, s in doc['sheets'].items():
    for p in s['viewports']:
        v = doc['views'].get(p['view']) or {}; c = v.get('crop') or {}
        if c.get('proj_method') != 2 or not c.get('bounds'): continue
        b = c['bounds']; pd = c.get('proj_dist') or 0.1
        tl, tr, tt, tb = b[0][1] / pd, b[0][0] / pd, b[1][0] / pd, b[1][1] / pd
        H = int(round(W * (tt - tb) / (tr - tl)))
        spec = {'view': v['id'], 'name': v['name'], 'sheet': s['sheetNumber'], 'eye': list(v['origin']), 'dir': list(v['dir']), 'tl': tl, 'tr': tr, 'tt': tt, 'tb': tb, 'size': [W, H],
                'viewport': {'offset': p.get('offset'), 'scale': p.get('scale')}}
        json.dump(spec, open(os.path.join(out, '%d.json' % v['id']), 'w'), indent=1); print(v['id'], v['name'], 'size', W, H, 'eye', [round(x, 2) for x in v['origin']])
