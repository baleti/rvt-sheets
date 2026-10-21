cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
rm -f ~/elem_prims_done.txt
python tools/elem_prims.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 124194 769857 611346 611347 > ~/elem_prims.txt 2>&1
echo DONE > ~/elem_prims_done.txt
