"""dim_classes.py FILE...: counts of record classes that look like annotation dimensions / symbols (bycls names containing Dim, Spot, Cloud, Keynote, Tag)"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
pat = re.compile(r'Dim|Spot|Cloud|Keynote|Tag|Revision|Leader|Callout|Matchline|Symbol', re.I)
for fn in sys.argv[1:]:
    try:
        d = Decoder(fn); c = {k: len(v) for k, v in d.f.bycls.items() if pat.search(k)}
        print(os.path.basename(fn), c, flush=True)
    except Exception as e: print(os.path.basename(fn), 'error', e, flush=True)
