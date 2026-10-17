#!/bin/bash
# robust_mem.sh FILE...: peak RSS of tools/robust.py (0 sheets, 12 views) with the record memo and the Rust hlr paths on / off, one process each (host1 job)
cd ~/src/rvt-sheets-dev
for f in "$@"; do
  for cfg in "RVT_FAST_REC_MEMO=1 RVT_NO_RUST_RASTER=0" "RVT_FAST_REC_MEMO=0 RVT_NO_RUST_RASTER=0" "RVT_FAST_REC_MEMO=1 RVT_NO_RUST_RASTER=1"; do
    echo "== $f $cfg"; env $cfg systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python tools/robust.py "$f" 0 12 2>&1 | tail -1 | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['seconds'], d['peak_rss_mb'], d.get('failures'), d.get('error'))"
  done
done
