"""prof_view.py FILE VIEWID [N]: cProfile of ViewDrawer.draw(view): top N functions by cumulative and own time"""
import sys, os, cProfile, pstats
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
d = Decoder(sys.argv[1]); doc = d.doc(); vd = ViewDrawer(d, doc); vid = int(sys.argv[2]); n = int(sys.argv[3]) if len(sys.argv) > 3 else 25
pr = cProfile.Profile(); pr.enable(); vd.draw(vid); pr.disable()
st = pstats.Stats(pr); st.sort_stats('cumulative').print_stats(n); st.sort_stats('tottime').print_stats(n)
