"""p5_probe.py FILE EID FIELD : keys / short values of a record field's object (recursive, depth 2)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); d.doc()
o = d.f.rec(int(sys.argv[2]))['fields'][sys.argv[3]]; o = o['obj'] if isinstance(o, dict) and 'obj' in o else o
for k, v in o.items(): print('P', k, str(v)[:200])
