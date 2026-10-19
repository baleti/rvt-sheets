"""zoff_probe.py FILE VIEWID: framing elements of a view grouped by class / z Offset Value / justification params"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
from rvtsheets.filters import FilterEval
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
vis = Visibility(dec, doc); fe = FilterEval(dec, doc)
shown, why = vis.elements(vid, explain=True)
g = collections.Counter(); ex = {}
keys = collections.Counter()
for eid in shown:
    e = vis.info.info[eid]
    if e['cat'] != -2001320: continue
    pe = (fe.params().get(eid) or {}).get('params') or {}
    k = (e['cls'], repr(pe.get('z Offset Value')), repr(pe.get('z Justification')), repr(pe.get('y Justification')))
    g[k] += 1; ex.setdefault(k, eid)
    for n in pe:
        if 'ustif' in n or 'ffset' in n: keys[n] += 1
for k, c in g.most_common(30): print(c, k, 'e.g.', ex[k])
print(keys)
pe = (fe.params().get(ex[g.most_common(1)[0][0]]) or {}).get('params') or {}
print(sorted(pe))
print('--- offsets by z Offset Value group')
h = collections.defaultdict(collections.Counter)
for eid in shown:
    e = vis.info.info[eid]
    if e['cat'] != -2001320: continue
    pe = (fe.params().get(eid) or {}).get('params') or {}
    z = pe.get('z Offset Value'); grp = 'None' if z is None else ('0' if z == 0 else 'nz')
    h[grp][(round(pe.get('Start Level Offset') or 0, 3), round(pe.get('End Level Offset') or 0, 3), round(pe.get('Start Offset') or 0, 3) if 'Start Offset' in pe else 'na', round(z, 3) if z else z)] += 1
for grp, c in h.items():
    print(grp, c.most_common(12))
