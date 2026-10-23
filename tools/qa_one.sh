#!/bin/bash
# qa_one.sh OUTDIR FILE_PREFIX VID...: host1: our SVG from this tree -> qa-view --svg; keeps the qa output dir (diff images) per view in OUTDIR
out=$1; f=$2; shift 2; mkdir -p $out
here=$(cd "$(dirname "$0")/.." && pwd); C=~/rvt-research/corpus; rvt=$(ls $C/*/$f* | head -1)
for v in "$@"; do
  python $here/tools/view_svg.py $rvt $v $out/$v.svg > $out/$v.log 2>&1
  (cd ~/src/rvt-qa; .venv/bin/python qa-view $rvt $v --svg $out/$v.svg --out $out/qa_$v 2>&1 | tail -n 12 > $out/$v.qa)
done
echo DONE > $out/DONE
