cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
rm -f ~/peak_rss.txt
for e in "" "RVT_TRANSP_OCC=0" "RVT_WALL_MESHFIX=0" "RVT_SOLID_FILL=0" "RVT_LINKS=0" "RVT_GRIDHEAD_DIR=0 RVT_DEDUPE=0"; do python tools/peak_rss.py $F 600158 $e >> ~/peak_rss.txt 2>&1; done
git -C ~/src/rvt-sheets-dev log --oneline -1 >> ~/peak_rss.txt
echo DONE >> ~/peak_rss.txt
