"""inventory of view/sheet related record classes in one file"""
import sys, os, collections
sys.path.insert(0, os.path.expanduser('~/rvt-research'))
import rvt_xcache
x = rvt_xcache.get_x(sys.argv[1])
recs = x['recs']
print('records', len(recs), 'keys sample', list(recs.items())[0][0], list(list(recs.items())[0][1].keys()))
cnt = collections.Counter(r['class'] for r in recs.values())
pat = sys.argv[2].lower().split(',') if len(sys.argv) > 2 else ['view', 'sheet', 'filter', 'templ', 'override', 'graphic', 'viewport', 'titleblock', 'schedule', 'legend', 'revision', 'phase', 'pattern', 'style', 'annot', 'tag', 'dim', 'text', 'detail', 'region', 'marker', 'callout', 'section', 'elev', 'crop', 'drawing', 'option', 'vis']
for c, n in sorted(cnt.items()):
    if any(p in c.lower() for p in pat): print('%6d %s' % (n, c))
