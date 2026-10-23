#!/bin/bash
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
python tools/check_elements.py ~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt 29154 > out/c10/ce29154.txt 2>&1
echo DONE
