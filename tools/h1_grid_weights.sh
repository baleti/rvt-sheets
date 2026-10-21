cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
G=$(ls -d ~/rvt-research/gt_views/2024_43_Snowdon_Towers_Sample_Structural* | head -1)
rm -f ~/grid_weights.txt
for v in 594746 124194 594716; do for e in 0 1; do echo "== $v TYPESTYLE=$e" >> ~/grid_weights.txt; RVT_GRID_TYPESTYLE=$e python tools/grid_weights.py $F $v $G/$v.dxf 2>&1 | grep -E "REVIT|OURS" >> ~/grid_weights.txt; done; done
echo DONE >> ~/grid_weights.txt
