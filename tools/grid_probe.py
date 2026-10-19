"""grid_probe.py FILE VIEWID: resolved graphics of the Grid / Level elements of a view (class counts, halftone, colour, weight, source)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.vg.resolve import resolve_view
dec = Decoder(sys.argv[1]); doc = dec.doc(); vid = int(sys.argv[2])
rep = resolve_view(dec, doc, vid, explain=True)
c = collections.Counter()
for eid, r in rep['elements'].items():
    if r['cls'] in ('Grid', 'Level'): c[(r['cls'], r['halftone'], str(r['proj']), tuple(sorted(r['source'].items())) and tuple(sorted(set(r['source'].values()))), tuple(r['filters']))] += 1
for k, n in c.most_common(): print(n, k)
print('template', rep['template'], 'filters', [(f['id'], f['name'], f['visible'], f['overrides']) for f in rep['filters'] if 'rid' in (f['name'] or '') or 'evel' in (f['name'] or '')])
