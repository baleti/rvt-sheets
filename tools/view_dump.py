"""view_dump.py FILE NAME_SUBSTR : print the decoded view dicts (without bulky keys) of views whose name contains NAME_SUBSTR"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
dec = Decoder(sys.argv[1]); doc = dec.doc()
for vid, v in doc['views'].items():
    if sys.argv[2].lower() in (v.get('name') or '').lower() and v.get('kind') == (sys.argv[3] if len(sys.argv) > 3 else v.get('kind')):
        print(vid, {k: (str(x)[:160]) for k, x in v.items() if k not in ('category_overrides', 'element_overrides', 'params', 'filters', 'draw_filters')})
        hc = __import__('rvtsheets.visibility', fromlist=['x']).Visibility(dec, doc).hidden_categories(v); print('  grids hidden', -2000220 in hc[0], 'levels hidden', -2000240 in hc[0], hc[1]); print('  section_box', v.get('section_box'))
