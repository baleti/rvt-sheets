"""floor_fields.py FILE EID... : decoded record field names/values of elements (scalar/id-like fields only)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
dec = Decoder(sys.argv[1]); f = dec.f
for eid in map(int, sys.argv[2:]):
    r = f.rec(eid); fl = r['fields']; h = f.eh.get(eid) or {}
    print(eid, r['class'], {k: v for k, v in list(fl.items()) if isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) < 40)}, '| hdr', {k: (v if isinstance(v, (int, float, bool, str)) else type(v).__name__) for k, v in h.items()}, flush=True)
