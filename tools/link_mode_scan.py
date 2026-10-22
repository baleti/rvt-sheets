"""link_mode_scan.py FILE... : per file, histogram of link display modes (overall HLE) over all views, and views whose mode is custom (2)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.vg import links
for fn in sys.argv[1:]:
    try:
        dec = Decoder(fn); doc = dec.doc(); f = dec.f
        n = len(f.recs('RvtLinkInstance')); c = collections.Counter(); cu = []
        for vid, v in doc['views'].items():
            fl = f.rec(vid)['fields']
            for sid, d in links.view_links(f, fl).items():
                for cs in [d['type_custom']] + list(d['instances'].values()):
                    if cs: c[cs['overall']] += 1; cu.append((vid, sid, cs['overall'])) if cs['overall'] == 'custom' else None
        print(os.path.basename(fn), 'instances', n, dict(c), cu[:4], flush=True)
    except Exception as ex:
        print(os.path.basename(fn), 'ERR', repr(ex)[:120], flush=True)
