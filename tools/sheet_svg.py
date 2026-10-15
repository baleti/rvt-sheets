"""sheet_svg.py FILE OUTDIR [sheet number...] -> OUTDIR/<number>.svg"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.sheet import SheetComposer
from rvtsheets.svg import drawing_svg
t = time.time(); dec = Decoder(sys.argv[1]); sc = SheetComposer(dec)
os.makedirs(sys.argv[2], exist_ok=True)
for sid, s in sc.doc['sheets'].items():
    if len(sys.argv) > 3 and s['sheetNumber'] not in sys.argv[3:]: continue
    dr = sc.compose(sid)
    open(os.path.join(sys.argv[2], '%s.svg' % s['sheetNumber']), 'w').write(drawing_svg(dr, sc.sty))
    print(s['sheetNumber'], s['name'], len(dr['prims']), 'prims', [p['text'] for p in dr['prims'] if p['t'] == 'note'])
print('%.1fs' % (time.time() - t))
