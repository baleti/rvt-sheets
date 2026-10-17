#!/bin/bash
# vg_multi.sh SCRIPT.py FILE... : run a per-file survey on each corpus file, sequentially (use through h1run: ~/.local/share/offload/h1run run NAME --env rvt -- tools/vg_multi.sh ...)
s=$1; shift; for f in "$@"; do echo "## $f"; timeout 900 ~/src/rvt-sheets/.venv/bin/python "$s" "$f" 2>&1 | tail -${TAILN:-20}; done
