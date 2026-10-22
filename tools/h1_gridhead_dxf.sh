cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
G=$(ls -d ~/rvt-research/gt_views/2024_43_Snowdon_Towers_Sample_Structural* | head -1)
rm -f ~/gridhead_dxf.txt
for v in 124194 594716 594746 124186; do for e in 0 1; do
  RVT_GRIDHEAD_DIR=$e python tools/compare_dxf.py $F $v $G/$v.dxf --register > ~/gh_tmp.txt 2>&1
  echo "$v DIR=$e $(grep -A2 '"S-GRID-IDEN"' ~/gh_tmp.txt | tr -d ' \n') $(grep -A2 '"datum"' ~/gh_tmp.txt | tr -d ' \n')" >> ~/gridhead_dxf.txt
done; done
echo DONE >> ~/gridhead_dxf.txt
