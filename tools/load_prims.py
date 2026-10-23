"""load_prims.py FILE VIEWID : classes of the elements in a view and, for load elements, what ViewDrawer draws (layers, prim types, counts)."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc)
vid = int(sys.argv[2]); dr = vd.draw(vid)
cls = {}
for e in doc['elements'].values() if isinstance(doc.get('elements'), dict) else []:
    pass
c = collections.Counter(); by = collections.defaultdict(collections.Counter)
for p in dr['prims']:
    el = p.get('elem')
    by[el][(p.get('layer'), p.get('t'))] += 1
print('prims', len(dr['prims']), 'keys', list(dr.keys()))
from rvtsheets.visibility import Visibility
els = Visibility(dec, doc).info.info
print('elements type', type(els), len(els))
n = 0
for el, cnt in by.items():
    info = els.get(el) if isinstance(els, dict) else None
    s = str((info or {}).get('cls')) + ' ' + str((info or {}).get('category'))
    if 'oad' in s:
        print(el, dict(cnt), s); n += 1
        if n > 15: break
cc = collections.Counter()
for el, cnt in by.items():
    info = els.get(el) or {}
    for k, n in cnt.items(): cc[(info.get('cls'), info.get('category'), k[0])] += n
for k, n in cc.most_common(25): print(k, n)
print('--- load-class elements in the file')
lc = collections.Counter((e.get('cls'), e.get('category')) for e in els.values() if 'oad' in str(e.get('cls')))
print(lc)
ex = [(i, e.get('cls'), e.get('level'), e.get('bbox')) for i, e in els.items() if 'oad' in str(e.get('cls'))][:6]
print(ex)
