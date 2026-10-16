"""robust.py FILE [max_sheets] [max_views] -> one JSON line: decode ok?, sheets/views counts, draw failures (first reason), seconds, peak RSS MB.
Drawing = the same code paths the server uses (compose.sheet_svg, viewdraw + viewsvg). Each item has a time limit (SIGALRM)."""
import sys, os, json, time, signal, resource, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
fn = sys.argv[1]; ms = int(sys.argv[2]) if len(sys.argv) > 2 else 3; mv = int(sys.argv[3]) if len(sys.argv) > 3 else 3
r = {'file': fn.replace(os.path.expanduser('~') + '/', ''), 'size_mb': round(os.path.getsize(fn) / 1e6, 1)}
t = time.time()
class TO(Exception): pass
def alarm(*a): raise TO('timeout')
signal.signal(signal.SIGALRM, alarm)
try:
    from rvtsheets.decode import Decoder
    from rvtsheets.viewdraw import ViewDrawer
    from rvtsheets.compose import sheet_svg
    from rvtsheets.viewsvg import view_svg
    dec = Decoder(fn); doc = dec.doc(); vd = ViewDrawer(dec, doc)
    r['decode_s'] = round(time.time() - t, 1)
    r['sheets'] = len(doc['sheets']); views = [v for v in doc['views'].values() if not v.get('template') and v.get('kind') in ('plan', 'section', 'drafting', 'legend', '3d')]
    r['views'] = len(views); r['view_errors_decode'] = sum(1 for v in doc['views'].values() if v.get('error'))
    fails = []; ok = 0; errs = {}
    items = [('sheet', s['id']) for s in list(doc['sheets'].values())[:ms]] + [('view', v['id']) for v in sorted(views, key=lambda v: (v['kind'] != 'plan', v['id']))[:mv]]
    for k, i in items:
        t1 = time.time(); signal.alarm(300)
        try:
            if k == 'sheet': s = sheet_svg(dec, i, doc, vd, log=lambda *a: None)
            else:
                dr_ = vd.draw(i); s = view_svg(dr_, doc['views'][i].get('scale') or 100)
                for kk, vv in (dr_.get('stats') or {}).items():
                    if 'error' in kk and vv: errs[kk] = errs.get(kk, 0) + vv      # internal swallowed errors per stat key
            ok += 1
        except Exception as ex:
            fails.append('%s %s: %s: %s' % (k, i, type(ex).__name__, str(ex)[:120]))
        finally: signal.alarm(0)
    r.update(drawn_ok=ok, drawn=len(items), failures=fails[:5], swallowed=errs)
except Exception as ex:
    r['error'] = '%s: %s' % (type(ex).__name__, str(ex)[:200]); r['trace'] = traceback.format_exc()[-600:]
r['seconds'] = round(time.time() - t, 1); r['peak_rss_mb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
print(json.dumps(r), flush=True)
