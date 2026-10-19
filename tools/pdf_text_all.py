"""pdf_text_all.py FILE [VIEWIDS...] : tools/pdf_text_diff.py for every view that has a Revit PDF in gt_views (or the given ids); one decode, one summary line per view,
details (ONLY REVIT / ONLY OURS) to stdout after. Output is long: redirect to a file."""
import sys, os, collections, glob, re, gc, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
fn = sys.argv[1]; base = os.path.splitext(os.path.basename(fn))[0]
gt = sorted(d for d in glob.glob(os.path.expanduser('~/rvt-research/gt_views/*')) if d.endswith(base) and os.path.isdir(d))[-1]
ids = [int(x) for x in sys.argv[2:]] or sorted(int(os.path.basename(p)[:-4]) for p in glob.glob(gt + '/*.pdf') if os.path.basename(p)[:-4].isdigit())
dec = Decoder(fn); doc = dec.doc(); d = ViewDrawer(dec, doc)
norm = lambda t: re.sub(r'\s+', ' ', t).strip()
res = []
for vid in ids:
    v = doc['views'].get(vid)
    if not v or v.get('kind') in ('sheet', 'schedule', 'legend') or vid in doc.get('sheets', {}): continue
    t = time.time()
    try:
        P = d.draw(vid)['prims']
        ours = collections.Counter(w for p in P if p['t'] == 'text' for x in p['text'].split('\n') for w in norm(x).split(' ') if w)
        page = pymupdf.open(os.path.join(gt, '%d.pdf' % vid))[0]
        rev = collections.Counter(); seen = set()
        for b in page.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                for s in l['spans']:
                    k = (s['text'], round(s['origin'][0]), round(s['origin'][1]))
                    if k in seen or not s['text'].strip(): continue
                    seen.add(k)
                    for w in norm(s['text']).split(' '):
                        if w: rev[w] += 1
        orv = collections.Counter({k: 1 for k in rev if k not in ours}); oou = collections.Counter({k: 1 for k in ours if k not in rev})      # SET difference: identical overlapping elements (duplicate dimensions) are drawn twice by both
        res.append((vid, v['name'], sum(rev.values()), sum(ours.values()), sum(orv.values()), sum(oou.values()), sorted(orv.items(), key=lambda x: -x[1])[:25], sorted(oou.items(), key=lambda x: -x[1])[:25]))
        print('%-9d %-34s revit %4d ours %4d onlyRevit %3d onlyOurs %3d  (%.0fs)' % (vid, v['name'][:34], res[-1][2], res[-1][3], res[-1][4], res[-1][5], time.time() - t), flush=True)
    except Exception as ex:
        print(vid, 'ERR', repr(ex)[:120], flush=True)
    gc.collect()
print('=== DETAILS')
for r in res:
    if r[4] or r[5]: print(r[0], r[1], '\n  ONLY REVIT', r[6], '\n  ONLY OURS', r[7])
