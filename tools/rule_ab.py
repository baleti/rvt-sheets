"""rule_ab.py FILE [SWITCH=VAL ...]: element-list FP/FN of one file with every listed env switch toggled alone (one decode): baseline (all new rules on), then each RVT_* switch set to 0 on its own"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets import oracle
fn = sys.argv[1]; o = oracle.load(oracle.find(fn)); dec = Decoder(fn); doc = dec.doc()
SW = ['RVT_ROOM_PHASE', 'RVT_ARROW_PHASE', 'RVT_MARKER_CROP', 'RVT_DEPENDENT', 'RVT_SECFLAG7', 'RVT_ROOM_NOBOX', 'RVT_LINK_NOBOX', 'RVT_PROPLINE_Z', 'RVT_MARKER_DISC']
def run(label, off=()):
    for k in SW: os.environ.pop(k, None)
    for k in off: os.environ[k] = '0'
    vis = Visibility(dec, doc); tp = fp = fn_ = 0; fpc = collections.Counter(); fnc = collections.Counter()
    for vid, ids in sorted(o['viewelems'].items()):
        v = doc['views'].get(vid)
        if not v or v.get('kind') in ('schedule', 'sheet'): continue
        P = set(vis.elements(vid)); G = set(ids); tp += len(P & G); fp += len(P - G); fn_ += len(G - P)
        for i in P - G: fpc[vis.info.info[i]['cls']] += 1
        for i in G - P: fnc[(vis.info.info.get(i) or {}).get('cls')] += 1
    print('%-22s P %.4f R %.4f fp %d fn %d  FP %s FN %s' % (label, tp / max(tp + fp, 1), tp / max(tp + fn_, 1), fp, fn_, fpc.most_common(5), fnc.most_common(4)), flush=True)
run('all new rules on')
run('all off', SW)
for k in SW: run('off ' + k, [k])
