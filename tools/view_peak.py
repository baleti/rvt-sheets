"""view_peak.py FILE [N] : peak RSS (MB) and seconds of drawing each of the first N views, one fresh process per view (host1 job)"""
import sys, os, json, subprocess, resource, time
fn = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
if len(sys.argv) > 3 and sys.argv[3] == '--one':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from rvtsheets.decode import Decoder
    from rvtsheets.viewdraw import ViewDrawer
    from rvtsheets.viewsvg import view_svg
    vid = int(sys.argv[4]); t = time.time()
    dec = Decoder(fn); doc = dec.doc(); r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    vd = ViewDrawer(dec, doc); dr = vd.draw(vid); view_svg(dr, doc['views'][vid].get('scale') or 100)
    print(json.dumps({'view': vid, 'name': doc['views'][vid]['name'], 'kind': doc['views'][vid]['kind'], 'base_mb': r0, 'peak_mb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, 'seconds': round(time.time() - t, 1)}))
    sys.exit(0)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rvtsheets.decode import Decoder
doc = Decoder(fn).doc()
views = [v for v in doc['views'].values() if not v.get('template') and v.get('kind') in ('plan', 'section', 'drafting', 'legend', '3d')]
views = sorted(views, key=lambda v: (v['kind'] != 'plan', v['id']))[:n]
for v in views:
    p = subprocess.run([sys.executable, os.path.abspath(__file__), fn, '0', '--one', str(v['id'])], capture_output=True, text=True)
    print(p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'ERR %s %s' % (v['id'], p.stderr.strip()[-120:]), flush=True)
