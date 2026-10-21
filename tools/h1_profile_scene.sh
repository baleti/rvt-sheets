cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
rm -f ~/prof_scene_done.txt
python tools/profile_scene.py ~/rvt-research/corpus/2024/46_Snowdon_Towers_Sample_Facades.rvt 29201 240 > ~/prof_scene.txt 2>&1
echo DONE > ~/prof_scene_done.txt
