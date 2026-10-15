#!/bin/bash
# h1dev.sh NAME CMD... : run CMD on host1 from the dev worktree (~/src/rvt-sheets-dev is not in h1run's sync list): rsync it with h1run's
# excludes, then `h1run run NAME --env rvt --dir DEV -- CMD`, retrying every 60 s while host1 is below h1run's memory guard (max 4 h)
dev=$(cd "$(dirname "$0")/.." && pwd); name=$1; shift
for i in $(seq 1 240); do
  ssh host1 "mkdir -p $dev" && rsync -a --exclude=.git --exclude=__pycache__ --exclude='.venv*' --exclude=out --exclude='*.rte' --exclude='*.rvt' "$dev/" "host1:$dev/"
  out=$(~/.local/share/offload/h1run run "$name" --env rvt --dir "$dev" -- "$@" 2>&1); echo "$out" | tail -2
  case "$out" in *busy*|*"could not start"*) sleep 60;; *) exit 0;; esac
done
exit 1
