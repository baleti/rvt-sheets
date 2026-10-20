"""dim_fp.py FILE VIEWID : dimension elements we list but Revit does not (owner view, id, class fields), plus a TP sample"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
vid = int(sys.argv[2]); pred = vis.elements(vid); G = set(o['viewelems'][vid])
def row(i):
    e = vis.info.info[i]; fl = dec.f.rec(i)['fields']
    return (i, e['cls'], 'owner', e['owner'], 'cat', e['cat'], 'phase', e['created'], 'dopt', e['dopt'], 'ws', fl.get('m_worksetId'), 'dimtype', fl.get('m_dimStyleId') or fl.get('m_typeId'), 'refs', str(fl.get('m_refs') or fl.get('m_references'))[:60])
fp = [i for i in pred if i not in G and vis.info.info[i]['cls'] == 'LinearDimString']
tp = [i for i in pred if i in G and vis.info.info[i]['cls'] == 'LinearDimString']
print('FP', len(fp), 'TP', len(tp))
for i in fp[:8]: print('FP', row(i))
for i in tp[:5]: print('TP', row(i))
P = vis._fe.params() if getattr(vis, '_fe', None) else __import__('rvtsheets.filters', fromlist=['x']).FilterEval(dec, doc).params()
v = doc['views'][vid]
print('view filters', [(vf['filter'], (doc['filters'].get(vf['filter']) or {}).get('name'), vf.get('visible'), vf.get('enabled')) for vf in v.get('filters') or []])
for tag, L in (('FP', fp[:3]), ('TP', tp[:3])):
    for i in L: print(tag, i, {k: x for k, x in ((P.get(i) or {}).get('params') or {}).items()})
from rvtsheets.reader import wref
_, why = vis.elements(vid, explain=True)
print('--- refs')
for tag, L in (('FP', fp[:10]), ('TP', tp[:6])):
    for i in L:
        fl = dec.f.rec(i)['fields']; refs = []
        for w in fl.get('m_witnessRefs') or []:
            try: refs.append(dec.f.eid((wref(w).get('m_geomRef') or {}).get('m_elemId')))
            except Exception: refs.append(None)
        print(tag, i, [(x, vis.info.info[x]['cls'] if x in vis.info.info else '-', 'rec' if (x is not None and dec.f.rec(x)) else 'norec', 'IN' if x in pred else why.get(x)) for x in refs])
