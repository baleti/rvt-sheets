"""profile_scene.py FILE VIEWID [SECONDS=240] : cProfile of rvtsheets.drawings.scene_text for one view (the viewer's /view/{id}.json), top cumulative functions; SIGALRM stops it after SECONDS"""
import sys, os, time, signal, cProfile, pstats
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.drawings import Model, scene_text
m = Model(os.path.abspath(sys.argv[1])); m.start()
while m.state in ('idle', 'loading'): time.sleep(0.5)
m.decoder(); vid = int(sys.argv[2]); lim = int(sys.argv[3]) if len(sys.argv) > 3 else 240
class Stop(Exception): pass
def h(*a): raise Stop()
signal.signal(signal.SIGALRM, h); signal.alarm(lim)
pr = cProfile.Profile(); t0 = time.time()
try: pr.runcall(scene_text, m, vid, {}); print('done in %.1fs' % (time.time() - t0))
except Stop: print('STOPPED after %ds' % lim)
signal.alarm(0)
pstats.Stats(pr).sort_stats('cumulative').print_stats(28)
