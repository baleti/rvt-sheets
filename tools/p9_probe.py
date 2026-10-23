"""p9_probe.py FILE VID... : schedule row counts with and without the schedule filters (RVT_SCHED_FILTER)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.sheet import SheetComposer
from rvtsheets.schedule import Schedules
d = Decoder(sys.argv[1]); doc = d.doc(); S = Schedules(SheetComposer(d, doc))
for vid in map(int, sys.argv[2:]):
    df = S.definition(vid)
    n = {}
    for e in ('0', '1'):
        os.environ['RVT_SCHED_FILTER'] = e; n[e] = len(S.rows(df))
    print('P', vid, df['name'], 'filters', [(a, b) for a, b, c in df['filters']], 'rows unfiltered', n['0'], 'filtered', n['1'])
    if len(sys.argv) > 2 and df['filters']:
        os.environ['RVT_SCHED_FILTER'] = '0'; a = S.rows(df); os.environ['RVT_SCHED_FILTER'] = '1'; b = S.rows(df)
        bs = [tuple(r) for r in b]; gone = [r for r in a if tuple(r) not in bs]
        print('P  removed sample', gone[:3]); print('P  kept sample', b[:3])
