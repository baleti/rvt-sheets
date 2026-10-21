cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
rm -f ~/prim_len2_done.txt
for v in 124194; do python tools/prim_lengths.py $F $v > ~/prim_len2_$v.txt 2>&1; done
echo DONE > ~/prim_len2_done.txt
