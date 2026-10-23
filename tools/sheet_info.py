"""sheet_info.py FILE: sheets with viewport lists and view kinds (is the sheet empty, which views are placed)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); doc = d.doc()
for sid, s in doc['sheets'].items():
    print(sid, s.get('sheetNumber'), repr(s.get('name')), 'viewports', len(s.get('viewports') or []), [(vp.get('view'), (doc['views'].get(vp.get('view')) or {}).get('kind')) for vp in (s.get('viewports') or [])][:8], 'titleblock', s.get('titleblock'))
print(len(doc['views']), 'views;', sorted({v.get('kind') for v in doc['views'].values()}))
