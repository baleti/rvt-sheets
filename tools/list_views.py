"""list_views.py FILE: view id, kind, name, scale for every non-sheet view"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); doc = d.doc()
for i, v in doc['views'].items(): print(i, v.get('kind'), repr(v.get('name')), v.get('scale'), 'tpl' if v.get('template') else '')
