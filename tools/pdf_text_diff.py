"""pdf_text_diff.py FILE VIEWID [GTDIR] : text strings of Revit's per-view PDF export vs ours (multiset diff, strings only): ONLY REVIT = missing / differently formatted,
ONLY OURS = extra. Reference = gt_views/<year_file>/<view>.pdf (vector text). Host1 (or host3 with ALLOW_HOST3=1 for one small view)."""
import sys, os, collections, glob, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
fn, vid = sys.argv[1], int(sys.argv[2])
base = os.path.splitext(os.path.basename(fn))[0]
gt = sys.argv[3] if len(sys.argv) > 3 else sorted(d for d in glob.glob(os.path.expanduser('~/rvt-research/gt_views/*')) if d.endswith(base) and os.path.isdir(d))[-1]
dec = Decoder(fn); doc = dec.doc(); d = ViewDrawer(dec, doc)
P = d.draw(vid)['prims']
norm = lambda t: re.sub(r'\s+', ' ', t).strip()
ours = collections.Counter(norm(t) for p in P if p['t'] == 'text' for t in p['text'].split('\n') if t.strip())
page = pymupdf.open(os.path.join(gt, '%d.pdf' % vid))[0]
rev = collections.Counter(); seen = set()
for b in page.get_text('dict')['blocks']:
    for l in b.get('lines', []):
        for s in l['spans']:
            k = (s['text'], round(s['origin'][0]), round(s['origin'][1]))
            if k in seen or not s['text'].strip(): continue
            seen.add(k); rev[norm(s['text'])] += 1
print('view', vid, doc['views'][vid]['name'], 'revit', sum(rev.values()), 'ours', sum(ours.values()))
print('ONLY REVIT', sorted((rev - ours).items(), key=lambda x: -x[1])[:60])
print('ONLY OURS', sorted((ours - rev).items(), key=lambda x: -x[1])[:60])
