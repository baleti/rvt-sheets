"""fp_attrs.py FILE.rvt VIEWID CLASS : attribute histogram (vflags, workset, phase, type, cat) of TP vs FP elements of a class in a view"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; vid = int(sys.argv[2]); klass = sys.argv[3]; o = oracle.load(oracle.find(fn))
dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
pred = set(vis.elements(vid)); G = set(o['viewelems'][vid])
def key(i):
    e = vis.info.info[i]; fl = dec.f.rec(i)['fields']; h = dec.f.eh.get(i) or {}
    return (e['vflags'], str(h.get('m_worksetId'))[:20], dec.f.eid(fl.get('m_symbolId') or fl.get('m_famId')), e['cat'])
for name, S in (('TP', pred & G), ('FP', pred - G)):
    c = collections.Counter(key(i) for i in S if vis.info.info[i]['cls'] == klass)
    print(name, sum(c.values())); [print('  ', k, n) for k, n in c.most_common(8)]
