"""elem_info.py FILE EID...: class, category, name, owner view and flags of elements (what is drawn for an id found in an SVG data-e attribute)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc)
for a in sys.argv[2:]:
    eid = int(a); e = vis.info.info.get(eid)
    if not e: print(eid, 'unknown'); continue
    r = dec.f.rec(eid); fl = (r or {}).get('fields') or {}
    print(eid, e['cls'], 'cat', e['cat'], (doc['categories'].get(e['cat']) or {}).get('name'), 'owner', e.get('owner'), 'flags', hex(fl.get('m_flags') or 0) if isinstance(fl.get('m_flags'), int) else None,
          'symbol', dec.f.eid(fl.get('m_symbolId')) if fl.get('m_symbolId') is not None else None, 'keys', sorted(fl)[:12])
