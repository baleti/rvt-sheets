"""vol_probe.py FILE VIEWID EID... : view range, the volume test and the exclusion reason of elements in one view"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
fn = sys.argv[1]; vid = int(sys.argv[2]); dec = Decoder(fn); doc = dec.doc(); vis = Visibility(dec, doc)
v = vis.effective(doc['views'][vid]); print('range', v.get('range'), 'kind', v['kind'])
vol = vis.volume(v); pred, why = vis.elements(vid, explain=True)
for e in map(int, sys.argv[3:]):
    bb = vis.info.bbox(e); print(e, vis.info.info[e]['cls'], 'bb z', None if bb is None else bb[:, 2].tolist(), 'vol', None if bb is None else vol(bb), 'listed', e in pred, why.get(e))
