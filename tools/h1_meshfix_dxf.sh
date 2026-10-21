cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
G=$(ls -d ~/rvt-research/gt_views/2024_43_Snowdon_Towers_Sample_Structural* | head -1)
for v in 124194 124186 594716 579975 843511; do
  for e in 0 1; do
    echo "== $v MESHFIX=$e" >> ~/meshfix_dxf.txt
    RVT_WALL_MESHFIX=$e python tools/compare_dxf.py $F $v $G/$v.dxf --register 2>&1 | grep -E '"precision"|"recall"|"ours_mm"' >> ~/meshfix_dxf.txt
  done
done
echo DONE >> ~/meshfix_dxf.txt
