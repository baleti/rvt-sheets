"""vp_owner.py FILE: Viewport records: owner view (sheet or not) histogram, view kinds, first few records' key fields"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); doc = d.doc(); f = d.f
c = collections.Counter(); k = collections.Counter()
for r in f.recs('Viewport', 'GCSViewport'):
    fl = r['fields']; own = f.eid(fl.get('m_ownerDBViewId')); v = f.eid(fl.get('m_dbViewId'))
    c[(own, (doc['views'].get(own) or {}).get('kind'))] += 1; k[(doc['views'].get(v) or {}).get('kind')] += 1
print('owners', c.most_common(8)); print('view kinds', dict(k))
r = f.recs('Viewport')[0]['fields']; print({kk: str(vv)[:50] for kk, vv in r.items() if not kk.startswith('m_pParam')})
print('sheets', [(i, s.get('sheetNumber')) for i, s in list(doc['sheets'].items())[:4]])
