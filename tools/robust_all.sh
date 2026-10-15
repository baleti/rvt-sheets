#!/bin/bash
# robust_all.sh OUT.jsonl : tools/robust.py over every corpus file, one process per file (sequential, 30 min cap, 4.5 GB cap each
# via a nested systemd scope so one big file cannot OOM the whole job); files already in OUT.jsonl are skipped (resume).
out=$1; mkdir -p "$(dirname "$out")"; touch "$out"
for f in $(ls ~/rvt-research/corpus/*/*.rvt ~/rvt-research/corpus/*/*.rte 2>/dev/null); do
  rel=${f#$HOME/}; grep -qF "\"file\": \"$rel\"" "$out" && continue
  timeout 1800 systemd-run --user --scope --quiet --slice=rvt-offload.slice -p MemoryMax=4500M -p MemorySwapMax=0 \
    python "$(dirname "$0")/robust.py" "$f" 3 3 >> "$out" 2>>"${out%.jsonl}.err" || echo "{\"file\": \"$rel\", \"error\": \"process exit $? (137 = memory cap 3.5 GB, 124 = 30 min timeout)\"}" >> "$out"
done
echo DONE >> "${out%.jsonl}.err"
