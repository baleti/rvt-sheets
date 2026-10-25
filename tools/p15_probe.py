"""p15_probe.py FILE VID : keys of the first schedule fields (find the totals flag)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.reader import ob
d = Decoder(sys.argv[1]); d.doc()
sch = ob(d.f.rec(int(sys.argv[2]), 'DBViewSchedule')['fields'].get('m_pSchema'))
for fd in sch['m_pFields']:
    o = ob(fd); print('P', {k: v for k, v in o.items() if not isinstance(v, (list, dict)) or k == 'm_headerIds'})
