cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
python tools/grid_surf.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 578141 598478 598556 > ~/grid_surf_snow.txt 2>&1
python tools/grid_surf.py ~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt $(python - <<'P'
P
) >> ~/grid_surf_snow.txt 2>&1
echo DONE >> ~/grid_surf_snow.txt
