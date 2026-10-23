#!/bin/bash
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt
{ for e in 149650 150522 191615 191723 152075 191765; do python tools/elem_geom.py $F $e 29154; done
python tools/elem_prims.py $F 29154 152075 191765; } > out/c10/cp2.txt 2>&1
echo DONE
