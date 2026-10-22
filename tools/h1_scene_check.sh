cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
rm -f ~/scene_check_done.txt
python tools/scene_check.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 600158 > ~/scene_check.txt 2>&1
echo DONE > ~/scene_check_done.txt
