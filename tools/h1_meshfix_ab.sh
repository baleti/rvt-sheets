cd ~/src/rvt-sheets-walker; export PATH=$HOME/rvt-env/bin:$PATH
for f in 2020/19_Commercial_Sample_Project.rvt 2020/20_Residential_Sample_Project.rvt 2024/43_Snowdon_Towers_Sample_Structural.rvt; do
  echo "== $f" >> ~/meshfix_ab.txt
  for e in 0 1; do RVT_WALL_MESHFIX=$e python - "$HOME/rvt-research/corpus/$f" >> ~/meshfix_ab.txt 2>&1 <<'P'
import sys, os, collections
sys.path.insert(0, os.path.expanduser('~/src/rvt-sheets-walker'))
from rvtsheets.decode import Decoder
from rvtsheets.viewdraw import ViewDrawer
dec = Decoder(sys.argv[1]); doc = dec.doc(); vd = ViewDrawer(dec, doc)
n = 0; tot = collections.Counter()
for vid, v in doc['views'].items():
    if v.get('kind') not in ('section', 'plan') or v.get('is_template'): continue
    try: dr = vd.draw(vid)
    except Exception as ex: continue
    tot['views'] += 1; tot['fix'] += dr['stats'].get('wall_meshfix', 0); tot['err'] += dr['stats'].get('wall_meshfix_error', 0)
print(os.environ.get('RVT_WALL_MESHFIX'), dict(tot))
P
  done
done
echo DONE >> ~/meshfix_ab.txt
