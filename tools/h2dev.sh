#!/bin/bash
# h2dev.sh NAME CMD... : like h1dev.sh but on host2 via h2run (no retry loop needed; host2 has spare memory). Syncs this worktree (any dev/c11 tree) first.
dev=$(cd "$(dirname "$0")/.." && pwd); name=$1; shift
ssh host2 "mkdir -p $dev" && rsync -a --exclude=.git --exclude=__pycache__ --exclude='.venv*' --exclude=out --exclude='*.rte' --exclude='*.rvt' "$dev/" "host2:$dev/"
~/.local/share/offload/h2run run "$name" --env rvt --dir "$dev" -- "$@"
