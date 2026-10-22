"""link_symbols.py FILE... : link types of a file (name, path, m_relative) and instance counts: which links the drawing may load (relative-path links are skipped: unloaded in Revit's exports)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.vg import links as L
from rvtsheets.vg.linkdraw import resolve_path
for fn in sys.argv[1:]:
    dec = Decoder(fn); dec.doc(); f = dec.f; types = L.link_types(f); insts = L.link_instances(f)
    print(os.path.basename(fn), 'link types', len(types), 'instances', len(insts))
    for sid, t in types.items():
        rel = (f.rec(sid) or {'fields': {}})['fields'].get('m_relative')
        print('  ', sid, t.get('name'), '|', t.get('path'), '| relative', rel, '| resolves to', resolve_path(fn, t.get('path') or t.get('name') or ''))
