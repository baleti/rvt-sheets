"""decode_doc.py FILE OUT.json -> decoded view/sheet model"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
t = time.time(); d = Decoder(sys.argv[1]).doc()
json.dump(d, open(sys.argv[2], 'w'), default=lambda o: int(o) if hasattr(o, '__int__') else repr(o), indent=None)
print('views', len(d['views']), 'sheets', len(d['sheets']), 'filters', len(d['filters']), '%.1fs' % (time.time() - t))
