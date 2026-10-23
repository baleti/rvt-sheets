"""p10_probe.py FILE VID : schedule schema scalar keys (itemize / totals / grouping flags) + field headings"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.reader import ob
d = Decoder(sys.argv[1]); d.doc()
sch = ob(d.f.rec(int(sys.argv[2]), 'DBViewSchedule')['fields'].get('m_pSchema'))
for k, v in sch.items():
    if not isinstance(v, (list, dict)) or k in ('m_sortFieldArr', 'm_filterArr', 'm_groupFieldArr'): print('P', k, str(v)[:200])
print('P fields', [(ob(x).get('m_columnHeading'), ob(x).get('m_bCalcTotals', ob(x).get('m_totals'))) for x in sch.get('m_pFields')])
