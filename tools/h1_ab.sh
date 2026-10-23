#!/bin/bash
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
python tools/curve_gs.py ~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt 196766 186475 2>&1 | tail -30
echo DONE
