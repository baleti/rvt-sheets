#!/bin/bash
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
python tools/curtain_probe.py ~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt 29154 area > out/c10/cp29154.txt 2>&1
echo DONE
