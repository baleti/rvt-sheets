#!/bin/bash
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
python tools/glaz_map.py ~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt 29154 ~/rvt-research/gt_views/2020_19_Commercial_Sample_Project/29154.dxf A-GLAZ-CWMG > out/c10/gm.txt 2>&1
echo DONE
