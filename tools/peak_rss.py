"""peak_rss.py FILE VIEWID [ENV=VAL ...] : draw one view in a child process with the given environment and print its peak RSS (MB) and seconds"""
import sys, os, subprocess, resource, time
f, vid, envs = sys.argv[1], sys.argv[2], sys.argv[3:]
env = dict(os.environ); env.update(dict(e.split('=', 1) for e in envs))
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
t = time.time(); r = subprocess.run([sys.executable, os.path.join(here, 'tools/view_svg.py'), f, vid, '/tmp/peak_rss.svg'], env=env, capture_output=True, text=True)
print('%-40s peak RSS %5d MB  %5.1fs  rc=%d' % (' '.join(envs) or 'baseline', resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss // 1024, time.time() - t, r.returncode), flush=True)
