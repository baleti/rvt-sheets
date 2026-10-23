#!/bin/bash
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
python tools/panel_gs.py ~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt 29154 149650 150522 191615 191723 152075 191765 > out/c10/pg.txt 2>&1
echo DONE
