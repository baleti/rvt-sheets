#!/bin/bash
# h1_glaz.sh : host1 job: Commercial East 29154 overlay of Revit's A-GLAZ-CWMG layer vs ours
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
python tools/dxf_overlay.py ~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt 29154 ~/rvt-research/gt_views/2020_19_Commercial_Sample_Project/29154.dxf out/c10/glaz29154.png A-GLAZ > out/c10/glaz29154.txt 2>&1
echo DONE
