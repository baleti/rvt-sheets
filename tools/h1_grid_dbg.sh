cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
RVT_GRID_DBG=1 python tools/view_svg.py $F 124194 /tmp/g124194.svg > ~/grid_dbg_snow.txt 2>&1
python tools/grid_ends.py $F 124194 >> ~/grid_dbg_snow.txt 2>&1
echo DONE >> ~/grid_dbg_snow.txt
