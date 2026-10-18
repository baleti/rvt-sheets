"""ws_probe.py FILE : where worksets live in the records (classes mentioning Workset, view settings, element header fields)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.reader import path
dec = Decoder(sys.argv[1]); f = dec.f
cl = collections.Counter(r['class'] for rs in f.byid.values() for r in rs)
print({k: n for k, n in cl.items() if 'orkset' in k or 'Partition' in k})
for r in f.recs('WorksetVisibilitySettingsElem'): print('WVS', r['id'], {k: str(v)[:300] for k, v in r['fields'].items() if k.startswith('m_inv') or 'orkset' in k})
for c in ('DBViewPlan',):
    for r in f.recs(c)[:40]:
        s = path(r['fields'], 'm_oWorksetVisibilityViewSettings')
        if s and s.get('m_worksetVisibilityPGUIDMap'): print('VIEW', r['id'], str(s)[:500])
eh = next(iter(f.eh.values())); print('eh keys', [k for k in eh if 'orks' in k or 'artit' in k])
ws = [k for k in next(iter(f.byid.values()))[0]['fields'] if 'orkset' in k or 'artition' in k]; print('rec fields', ws)
for r in list(f.recs('SWall'))[:3]: print('wall', r['id'], {k: str(v)[:80] for k, v in r['fields'].items() if 'orkset' in k.lower() or 'partition' in k.lower()}, {k: str(v)[:80] for k, v in (f.eh.get(r['id']) or {}).items() if 'orkset' in k.lower() or 'partition' in k.lower()})
