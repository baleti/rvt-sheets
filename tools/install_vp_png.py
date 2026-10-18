"""install_vp_png.py FILE.rvt VIEWID IMAGE.png : use IMAGE.png (the viewer's render of that perspective 3D view, same crop as the sheet viewport) in place of our software shading
on every sheet that shows the view. Stored under ~/.cache/rvt-sheets/vp3d/<file sha1>/<viewid>.png (local cache only, never committed); re-run `rvt-sheets warm --refresh` afterwards.
Remove the file (or RVT_VP_PNG=0) to go back to the software render."""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.cache import file_hash, ROOT
fn, vid, png = sys.argv[1:4]
d = os.path.join(ROOT, 'vp3d', file_hash(os.path.abspath(fn))); os.makedirs(d, exist_ok=True)
shutil.copy(png, os.path.join(d, '%d.png' % int(vid))); print('installed', os.path.join(d, '%d.png' % int(vid)))
