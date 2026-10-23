#!/bin/bash
# robust_dir.sh OUT.jsonl DIR : tools/robust.py over every .rvt / .rte under DIR (host1 job, like robust_all.sh: one process per file, 30 min cap, 4.5 GB cap, resumes)
out=$1; dir=$2; mkdir -p "$(dirname "$out")"; touch "$out"
find "$dir" \( -name '*.rvt' -o -name '*.rte' \) -size +300k | sort | while read -r f; do
  grep -qF "\"file\": \"$f\"" "$out" && continue
  timeout 1800 systemd-run --user --scope --quiet --slice=rvt-offload.slice -p MemoryMax=${CAP:-4500M} -p MemorySwapMax=0 \
    python "$(dirname "$0")/robust.py" "$f" 3 3 >> "$out" 2>>"${out%.jsonl}.err" || echo "{\"file\": \"$f\", \"error\": \"process exit $? (137 = memory cap, 124 = 30 min timeout)\"}" >> "$out"
done
echo DONE >> "${out%.jsonl}.done"
