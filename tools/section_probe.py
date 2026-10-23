"""section_probe.py FILE SECTIONID...: section marker inputs: view, view type, SectionAttributes head / tail ids and what the head symbol resolves to"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); doc = d.doc(); f = d.f
for e in [int(a) for a in sys.argv[2:]]:
    r = f.rec(e, 'Section'); fl = r['fields']
    tv = f.eid(fl.get('m_dbViewId')); vrec = f.rec(tv)
    vt = f.rec(f.eid(vrec['fields'].get('m_dbViewTypeId'))) if vrec else None
    at = f.rec(f.eid(vt['fields'].get('m_sectionAttrId'))) if vt else None
    af = at['fields'] if at else {}
    print(e, 'view', tv, vrec and vrec['class'], 'vtype', vt and vt['id'], 'attr', at and at['id'], {k: str(v)[:40] for k, v in af.items() if 'ection' in k or 'ymbol' in k or 'amily' in k})
    for k in ('m_sectionHeadFamilyTagId', 'm_sectionTailFamilyTagId'):
        sid = f.eid(af.get(k)); g = f.graphics(sid) if sid not in (None, -1) else None
        print('   ', k, sid, f.rec(sid) and f.rec(sid)['class'], g and g.get('class'))
