"""cloud_probe.py FILE: RevisionCloud elements: owner view (kind, name), revision, sketch curve elements, graphics class of the cloud and its curves, listed in the view?, prims drawn for them"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
d = Decoder(sys.argv[1]); doc = d.doc(); f = d.f; vis = Visibility(d, doc); I = vis.info.info
by = collections.defaultdict(list)
for r in f.recs('RevisionCloud'): by[f.eid(r['fields'].get('m_ownerDBViewId'))].append(r['id'])
for vid, ids in sorted(by.items(), key=lambda kv: -len(kv[1]))[:8]:
    v = doc['views'].get(vid) or {}
    try: l = set(vis.elements(vid))
    except Exception: l = set()
    r = f.rec(ids[0]); sk = f.rec(f.eid(r['fields']['m_sketchId']))
    cur = [x['m_elementId'] for x in (sk['fields'].get('m_elemIdsPairSet') or {}).get('obj', {}).get('m_data', [])] if sk else []
    g = f.graphics(ids[0])
    print(vid, v.get('kind'), repr(v.get('name')), 'clouds', len(ids), 'listed', sum(i in l for i in ids), 'sketch curves', len(cur), [f.rec(f.eid(c))['class'] if f.rec(f.eid(c)) else None for c in cur][:4], 'cloud gfx', g and g.get('class'))
