"""vg_report.py FILE.rvt VIEWID [OUT.json] -> graphics resolution report of a view (rvtsheets.vg.resolve): template, filters, per-element override stack."""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.vg.resolve import resolve_view
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
rep = resolve_view(dec, doc, vid, explain=True)
els = rep['elements']
print(rep['name'], rep['kind'], 'template', rep['template'] and rep['template']['name'], 'elements', len(els), 'excluded', rep['excluded'])
print('filters', [(f['name'], f['visible']) for f in rep['filters']])
print('with overrides', sum(1 for e in els.values() if e['overrides']), 'by source', collections.Counter(s.split(':')[0] for e in els.values() for s in set(e['source'].values())))
print('filter hits', collections.Counter(f for e in els.values() for f in e['filters']))
if len(sys.argv) > 3: json.dump(rep, open(sys.argv[3], 'w'), default=int)
