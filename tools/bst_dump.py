"""bst_dump.py FILE VIEWID : BeamSystemTag / SpanDirectionSymbol records of a view: scalar fields, orientation cell, symbol params, our text prims (host1)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.reader import ob
dec = Decoder(sys.argv[1]); doc = dec.doc(); d = ViewDrawer(dec, doc); f = d.f
dr = d.draw(int(sys.argv[2]))
n = 0
for e, i in d.vis.info.info.items():
    if i['cls'] in ('BeamSystemTag', 'SpanDirectionSymbol') and i['owner'] == int(sys.argv[2]):
        r = f.rec(e); fl = r['fields']; n += 1
        if n > 6: break
        print('==', e, i['cls'])
        for k, v in fl.items():
            s = json.dumps(v, default=repr) if isinstance(v, (dict, list)) else repr(v)
            if v not in (None, [], {}) and not k.startswith('m_pGeom'): print('  ', k, s[:260])
        sid = f.eid(fl.get('m_actualSymbolId')) or f.eid(fl.get('m_symbolId'))
        print('   symbol params', d.tags.symbol_params(sid) if hasattr(d, 'tags') else '')
        print('   ours', [(p['text'], [round(x, 2) for x in p['origin']], [round(x, 2) for x in p['x']]) for p in dr['prims'] if p.get('elem') == e and p['t'] == 'text'])
