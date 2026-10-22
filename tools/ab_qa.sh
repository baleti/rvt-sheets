#!/bin/bash
# ab_qa.sh OUT.txt ENVVAR "FILE:VID FILE:VID ..." : host1 A/B of one env switch (0 vs 1) over views: our SVG from this tree -> qa-view --svg score / ssim / ink P3 / R3
out=$1; var=$2; shift 2; : > $out
here=$(cd "$(dirname "$0")/.." && pwd); C=~/rvt-research/corpus; S=$(mktemp -d)
for fv in $1; do
  f=${fv%%:*}; v=${fv##*:}; rvt=$(ls $C/*/$f* | head -1)
  for e in 0 1; do
    env $var=$e python $here/tools/view_svg.py $rvt $v $S/v.svg > /dev/null 2>&1
    r=$(cd ~/src/rvt-qa; .venv/bin/python qa-view $rvt $v --svg $S/v.svg --out $S/qa 2>&1 | grep "^SCORE\|^summary" | tr '\n' ' ' | cut -c1-140)
    echo "$f $v $var=$e $r" >> $out
  done
done
echo DONE >> $out
