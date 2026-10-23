#!/bin/bash
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt
python tools/walk_probe.py $F 29154 149650 150522 191615 191723 152075 > out/c10/cp3.txt 2>&1
python tools/elem_info.py $F 149650 152075 >> out/c10/cp3.txt 2>&1
echo DONE
