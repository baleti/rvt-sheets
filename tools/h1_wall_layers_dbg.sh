cd ~/src/rvt-sheets-dev; export PATH=$HOME/rvt-env/bin:$PATH
rm -f ~/wl_done.txt
python tools/wall_layers_dbg.py ~/rvt-research/corpus/2026/58_Snowdon_Towers_Sample_Facades.rvt 607489 > ~/wl.txt 2>&1
echo DONE > ~/wl_done.txt
