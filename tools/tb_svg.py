"""tb_svg.py OUTDIR FILE:SHEET_ID [FILE:SHEET_ID ...] -> OUTDIR/<n>.svg: sheets composed without viewport content (titleblock, schedules, sheet-level text), cheap host1 job"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.sheet import SheetComposer
from rvtsheets.svg import drawing_svg
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
for i, a in enumerate(sys.argv[2:]):
    fn, sid = a.rsplit(':', 1)
    dec = Decoder(os.path.expanduser(fn)); sc = SheetComposer(dec)
    open(os.path.join(out, '%d_%s.svg' % (i, sid)), 'w').write(drawing_svg(sc.compose(int(sid)), sc.sty))
