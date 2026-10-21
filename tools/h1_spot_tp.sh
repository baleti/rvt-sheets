cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
for v in 124186 124194 594716; do
 RVT_SPOT_DBG=1 TP_DETAIL=G-ANNO-DIMS python tools/text_pairs.py $F $v > ~/spot_tw_$v.txt 2>&1
done; echo DONE >> ~/spot_tw_594716.txt
