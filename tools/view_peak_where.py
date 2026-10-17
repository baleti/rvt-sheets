"""view_peak_where.py FILE VIEW : draws one view and prints the python stack (innermost 6 frames) each time process RSS reaches a new maximum (>100 MB steps), to find what allocates the peak (host1 job)"""
import sys, os, threading, time, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
from rvtsheets.viewsvg import view_svg
fn, vid = sys.argv[1], int(sys.argv[2])
def rss():
    with open('/proc/self/statm') as f: return int(f.read().split()[1]) * 4096 // 2**20
main = threading.main_thread().ident; best = [0]; stop = [False]
def sampler():
    while not stop[0]:
        r = rss()
        if r > best[0] + 100:
            best[0] = r; fr = sys._current_frames().get(main)
            st = traceback.extract_stack(fr)[-6:] if fr else []
            print('RSS %d MB: ' % r + ' < '.join('%s:%d %s' % (os.path.basename(s.filename), s.lineno, s.name) for s in reversed(st)), flush=True)
        time.sleep(0.15)
dec = Decoder(fn); doc = dec.doc()
th = threading.Thread(target=sampler, daemon=True); th.start()
dr = ViewDrawer(dec, doc).draw(vid); view_svg(dr, doc['views'][vid].get('scale') or 100)
stop[0] = True; print('done peak', best[0])
