#!/bin/bash
# ab_dxf.sh ENVVAR OUTPREFIX dxf_all.sh|dxf_all_snow.sh : host1 A/B of one env switch over all gt DXF views (0 then 1) -> OUTPREFIX0.tsv / OUTPREFIX1.tsv
var=$1; pre=$2; script=$3; here=$(cd "$(dirname "$0")" && pwd)
for e in 0 1; do env $var=$e bash $here/$script ${pre}$e.tsv; done
