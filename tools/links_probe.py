"""links_probe.py FILE : per view, link override keys and key settings (compare with LINKOVR rows of the .vg dump)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.reader import path
from rvtsheets.vg import links as L
dec = Decoder(sys.argv[1]); f = dec.f; doc = dec.doc()
print('types', L.link_types(f)); print('instances', {k: v['symbol'] for k, v in L.link_instances(f).items()})
for r in f.recs('DBViewPlan'):
    lo = path(r['fields'], 'm_pRvtLinkOverrides') or {}
    if lo.get('m_invisibleSet') or lo.get('m_halftoneSet') or lo.get('m_underlaySet') or lo.get('m_displaySettingsMap'):
        print(r['id'], doc['views'][r['id']]['name'], 'inv', [f.eid(x) for x in lo.get('m_invisibleSet') or []], 'ht', [f.eid(x) for x in lo.get('m_halftoneSet') or []],
              'keys', [(f.eid(p['first']), p['second'].get('m_overallHLE'), p['second'].get('m_modelHLE'), p['second'].get('m_linkedView')) for p in lo.get('m_displaySettingsMap') or []])
