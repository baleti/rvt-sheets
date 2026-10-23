"""p4_probe.py FILE EID... : non-parameter record fields of the elements (short)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); d.doc()
for e in map(int, sys.argv[2:]):
    r = d.f.rec(e); print('P', e, r['class'])
    for k, v in r['fields'].items():
        if k.startswith('m_pParam') or k in ('m_docAccess', 'm_cellList', 'm_geomSteps', 'm_pGeomTable', 'm_constrInfo'): continue
        print('P  ', k, str(v)[:160])
