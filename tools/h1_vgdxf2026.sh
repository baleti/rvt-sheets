#!/bin/bash
# h1_vgdxf2026.sh : host1 job: tools/vg_dxf_all.sh for the 2026 oracle scenes (PY = host1 env)
cd "$(dirname "$0")/.."; PY=$HOME/rvt-env/bin/python tools/vg_dxf_all.sh 2026
