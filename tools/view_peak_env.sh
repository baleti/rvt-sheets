#!/bin/bash
# view_peak_env.sh FILE VIEW VAR=val ... : peak RSS of one view with env variants (host1 job); runs each variant in its own process
cd ~/src/rvt-sheets-dev
f=$1; v=$2; shift 2
for cfg in "$@"; do echo "== $cfg"; env $cfg python tools/view_peak.py "$f" 0 --one "$v" 2>&1 | tail -1; done
