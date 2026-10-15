"""sheet_full.py FILE OUTDIR [sheet numbers...] -> OUTDIR/<number>.svg with view content"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.compose import sheet_svg
dec = Decoder(sys.argv[1]); doc = dec.doc(); os.makedirs(sys.argv[2], exist_ok=True)
for sid, s in doc['sheets'].items():
    if len(sys.argv) > 3 and s['sheetNumber'] not in sys.argv[3:]: continue
    t = time.time(); print(s['sheetNumber'], s['name'])
    open(os.path.join(sys.argv[2], s['sheetNumber'] + '.svg'), 'w').write(sheet_svg(dec, sid, doc))
    print('  %.1fs' % (time.time() - t))
