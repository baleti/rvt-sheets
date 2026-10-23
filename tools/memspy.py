"""memspy.py FILE VIEWID: samples RSS every 0.1 s while Visibility.elements(view) runs and prints the main thread's innermost rvtsheets frames each time RSS grew by >= 150 MB (where the memory goes)"""
import sys, os, time, threading, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def rss():
    for l in open('/proc/self/status'):
        if l.startswith('VmRSS'): return int(l.split()[1]) // 1024
main = threading.main_thread().ident; last = [rss()]; stop = [False]
def spy():
    while not stop[0]:
        r = rss()
        if r - last[0] >= 150:
            fr = sys._current_frames().get(main); st = traceback.extract_stack(fr)
            tail = [f'{os.path.basename(s.filename)}:{s.lineno}:{s.name}' for s in st if 'rvtsheets' in s.filename or 'rvt_' in s.filename][-6:]
            print('RSS %d (+%d)' % (r, r - last[0]), ' > '.join(tail), flush=True); last[0] = r
        time.sleep(0.1)
threading.Thread(target=spy, daemon=True).start()
from rvtsheets.decode import Decoder
from rvtsheets.visibility import Visibility
d = Decoder(sys.argv[1]); doc = d.doc(); vis = Visibility(d, doc); last[0] = rss()
l = vis.elements(int(sys.argv[2])); print('elements', len(l), 'rss', rss(), flush=True)
if len(sys.argv) > 3:
    from rvtsheets.viewdraw import ViewDrawer
    vd = ViewDrawer(d, doc); vd.draw(int(sys.argv[2])); print('drawn rss', rss(), flush=True)
stop[0] = True
