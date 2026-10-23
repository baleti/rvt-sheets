"""memtrace.py FILE [VIEWID]: RSS (MB) after each stage (decode, doc, visibility, first sheet / given view draw): where a big file peaks"""
import sys, os, time, resource
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def rss():
    for l in open('/proc/self/status'):
        if l.startswith('VmRSS'): return int(l.split()[1]) // 1024
def mark(s, t0=[time.time()]): print('%-28s rss %5d MB peak %5d MB  %.1fs' % (s, rss(), resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, time.time() - t0[0]), flush=True)
fn = sys.argv[1]
from rvtsheets.decode import Decoder
d = Decoder(fn); mark('Decoder')
doc = d.doc(); mark('doc (%d views, %d sheets)' % (len(doc['views']), sum(1 for v in doc['views'].values() if v.get('kind') == 'sheet')))
from rvtsheets.visibility import Visibility
vis = Visibility(d, doc); mark('Visibility')
vid = int(sys.argv[2]) if len(sys.argv) > 2 else next((i for i, v in doc['views'].items() if v.get('kind') == 'plan'), None)
if vid is not None:
    l = vis.elements(vid); mark('elements view %s (%d)' % (vid, len(l)))
    from rvtsheets.viewdraw import ViewDrawer
    vd = ViewDrawer(d, doc); dr = vd.draw(vid); mark('draw view %s' % vid)
