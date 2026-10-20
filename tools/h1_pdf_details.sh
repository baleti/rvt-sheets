#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
python tools/pdf_text_all.py ~/rvt-research/corpus/2024/46_Snowdon_Towers_Sample_Facades.rvt 607540 > ~/pdf_det.txt 2>&1
RVT_ARROW_PHASE=0 python tools/pdf_text_all.py ~/rvt-research/corpus/2024/46_Snowdon_Towers_Sample_Facades.rvt 607540 > ~/pdf_det_noarrow.txt 2>&1
RVT_MARKER_CROP=0 python tools/pdf_text_all.py ~/rvt-research/corpus/2024/46_Snowdon_Towers_Sample_Facades.rvt 607540 > ~/pdf_det_nocrop.txt 2>&1
RVT_ROOM_PHASE=0 RVT_DEPENDENT=0 RVT_SECFLAG7=0 python tools/pdf_text_all.py ~/rvt-research/corpus/2024/46_Snowdon_Towers_Sample_Facades.rvt 607540 > ~/pdf_det_other.txt 2>&1
echo DONE > ~/pdf_det.done
