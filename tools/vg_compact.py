"""vg_compact.py FILE.rvt VIEWID OUT.json [full] -> compact graphics resolution (rvtsheets.vg.api.compact_text) with size statistics"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.vg.api import compact_text
dec = Decoder(sys.argv[1]); doc = dec.doc(); t = compact_text(dec, doc, int(sys.argv[2]), full=len(sys.argv) > 4)
open(sys.argv[3], 'w').write(t); d = json.loads(t)
print('bytes', len(t), 'styles', len(d['styles']), 'cat_style', len(d['cat_style']), 'overridden elements', len(d['elements']), 'fill_patterns', len(d['fill_patterns']), 'materials', len(d['materials']))
