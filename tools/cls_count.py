"""cls_count.py FILE [substr...]: record counts per class (filtered by substrings), plus the Revit version"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); f = d.f
print('version', getattr(f, 'version', None) or getattr(f, 'ver', None), 'classes', len(f.bycls))
for k, v in sorted(f.bycls.items(), key=lambda kv: -len(kv[1])):
    if len(sys.argv) == 2 or any(s.lower() in k.lower() for s in sys.argv[2:]): print(k, len(v))
