"""ws_probe2.py FILE WALLID : all header keys + rec top-level keys of an element, and any global streams mentioning guids/worksets"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
dec = Decoder(sys.argv[1]); f = dec.f; w = int(sys.argv[2])
print('eh', {k: str(v)[:60] for k, v in (f.eh.get(w) or {}).items() if k != 'm_regenHistory'})
print('rec', [k for k in f.rec(w)['fields']])
print('rec meta', {k: str(v)[:80] for k, v in f.rec(w).items() if k != 'fields'})
print([a for a in dir(f) if not a.startswith('_')][:60])
