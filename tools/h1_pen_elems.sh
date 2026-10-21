cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
rm -f ~/pen_elems_done.txt
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
for w in 0.305 0.635 0.127; do echo "== $w" >> ~/pen_elems.txt; python tools/pen_elems.py $F 124194 $w >> ~/pen_elems.txt 2>&1; done
echo DONE > ~/pen_elems_done.txt
