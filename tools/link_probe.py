"""link_probe.py FILE: RvtLinkInstance / RvtLinkSymbol scalar fields, bbox and the views listing them"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
dec = Decoder(sys.argv[1]); doc = dec.doc(); vis = Visibility(dec, doc); f = dec.f
o = None
try: o = oracle.load(oracle.find(sys.argv[1]))
except Exception: pass
def sc(fl): return {k: (str(v)[:60]) for k, v in fl.items() if not isinstance(v, (dict, list)) and v is not None and k not in ('m_id',) and not k.startswith('m_pParam')}
for e, i in vis.info.info.items():
    if i['cls'] in ('RvtLinkInstance', 'RvtLinkSymbol'):
        fl = f.rec(e)['fields']; n = sum(1 for ids in (o or {'viewelems': {}})['viewelems'].values() if e in ids)
        print(i['cls'], e, 'bbox', None if vis.info.bbox(e) is None else 'yes', 'gt views listing', n, sc(fl))
