"""dopt_scan.py FILE... : views (and templates) that carry a per-view design option choice (m_mOverridingOptions2), plus the file's option sets"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
for fn in sys.argv[1:]:
    try:
        dec = Decoder(fn); doc = dec.doc()
        sets = [(r['id'], dec.f.eid(r['fields'].get('m_mainDesignOption'))) for r in dec.f.recs('DesignOptionSet')]
        opts = len(dec.f.recs('DesignOption'))
        vs = [(vid, v['name'], v['design_options']) for vid, v in doc['views'].items() if v.get('design_options')]
        print(os.path.basename(fn), 'sets', sets, 'options', opts, 'views_with_choice', len(vs), vs[:6], flush=True)
    except Exception as ex:
        print(os.path.basename(fn), 'ERR', repr(ex)[:120], flush=True)
