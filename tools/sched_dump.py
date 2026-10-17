"""sched_dump.py FILE SHEET_ID [GT_DXF] : schedule definitions on a sheet (fonts, grid, row heights), our text prim sizes, and the Revit DXF text heights (host1 job for big files)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.sheet import SheetComposer
from rvtsheets.schedule import Schedules
fn, sid = sys.argv[1], int(sys.argv[2])
dec = Decoder(fn); doc = dec.doc(); sc = SheetComposer(dec, doc)
sheet = doc['sheets'].get(sid) or doc['sheets'].get(str(sid)); S = Schedules(sc)
for si in sheet.get('schedules') or []:
    d = S.definition(si['schedule'])
    if not d: continue
    pr = S.prims(si['schedule'], si['origin'] or [0, 0, 0], sid)
    sz = collections.Counter(round(p['size'], 5) for p in pr if p['t'] == 'text')
    ys = [pt[1] for p in pr if p['t'] == 'line' for pt in p['pts']] + [p['origin'][1] for p in pr if p['t'] == 'text']; xs = [pt[0] for p in pr if p['t'] == 'line' for pt in p['pts']]
    print('bbox ft x', round(min(xs or [0]), 3), round(max(xs or [0]), 3), 'y', round(min(ys or [0]), 3), round(max(ys or [0]), 3), 'stored height', d['height'], 'origin', si['origin'], 'sheet extent', sheet.get('extent'))
    print(si['schedule'], d['name'], 'grid', d['grid_lines'], 'title_h', d['title_h'], 'body_h', d['body_h'], 'fonts', d['fonts'], 'ours', dict(sz), 'rows', sum(1 for p in pr if p['t'] == 'text'))
if len(sys.argv) > 3 and sys.argv[3] != '-':
    import ezdxf
    dx = ezdxf.readfile(sys.argv[3]); K = {1: 1/12, 2: 1.0, 4: 1/304.8, 5: 1/30.48, 6: 1/0.3048}.get(dx.header.get('$INSUNITS', 0), 1.0)
    h = collections.Counter()
    for e in dx.modelspace():
        if e.dxftype() in ('TEXT', 'MTEXT'): h[round(e.dxf.get('height', e.dxf.get('char_height', 0)) * K, 5)] += 1
    print('revit dxf text heights (ft):', dict(h))
