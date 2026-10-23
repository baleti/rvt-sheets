"""p12_probe.py FILE : sheets and the schedules they carry"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
d = Decoder(sys.argv[1]); doc = d.doc()
for sid, s in doc['sheets'].items():
    for si in s.get('schedules') or []: print('P', sid, s['sheetNumber'], s['name'], si['schedule'], doc['views'].get(si['schedule'], {}).get('name'))
