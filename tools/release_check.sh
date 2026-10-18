#!/bin/bash
# release_check.sh : the release smoke in ONE host1 job (host3 is the user's daily driver, never run this there):
#   ~/.local/share/offload/h1run run NAME --env rvt --dir $PWD -- bash tools/release_check.sh
# cache completeness of the 5 demo files (after `warm --host1`) + snowdon_l2_check; last line 'RELEASE CHECK OK' or 'RELEASE CHECK FAILED'
cd "$(dirname "$0")/.." || exit 1
export SMOKE_SHEETS_ONLY=1      # host1 has no viewer runtime: the standalone /sheets/ server stage only (the viewer demo command is checked on the demo machine)
C=~/rvt-research/corpus; ok=1
FILES=""; for f in 2020/20_Residential_Sample_Project.rvt 2020/19_Commercial_Sample_Project.rvt 2026/77_Construction-DefaultMetric.rte 2024/43_Snowdon_Towers_Sample_Structural.rvt 2026/58_Snowdon_Towers_Sample_Facades.rvt; do FILES="$FILES $C/$f"; done
python tools/cache_check.py $FILES || ok=0      # server smoke needs aiohttp (not on host1): run tools/smoke.sh for ONE file on the demo machine
python tools/snowdon_l2_check.py 2>&1 | tail -1 | grep -q "ALL OK" && echo "snowdon_l2_check ALL OK" || { echo "snowdon_l2_check FAILED"; ok=0; }
[ $ok = 1 ] && echo "RELEASE CHECK OK" || echo "RELEASE CHECK FAILED"
