#!/bin/bash
cd ~/src/rvt-sheets-dev
for f in 2024/43_Snowdon_Towers_Sample_Structural 2017/05_rme_advanced_sample_project 2026/58_Snowdon_Towers_Sample_Facades; do
  ext=rvt; [ -f ~/rvt-research/corpus/$f.rvt ] || ext=rte
  for memo in 0 1; do echo "memo=$memo"; RVT_FAST_REC_MEMO=$memo python tools/robust.py ~/rvt-research/corpus/$f.$ext 2 4; done
done
