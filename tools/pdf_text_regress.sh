#!/bin/bash
# pdf_text_regress.sh [update] : Revit-PDF word diff (tools/pdf_text_all.py) over the Snowdon 2024 / 2026 Structural + Facades files and the 2026 annotation scenes;
# compares the per-view (onlyRevit onlyOurs) numbers with tools/pdf_text.baseline (any view that got worse is listed); 'update' rewrites the baseline. Heavy: host1 (or host3 one file at a time with ALLOW_HOST3=1).
cd "$(dirname "$0")/.."; PY=${PY:-python}; C=~/rvt-research
out=$(mktemp)
for f in $C/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt $C/corpus/2024/46_Snowdon_Towers_Sample_Facades.rvt $C/corpus/2026/55_Snowdon_Towers_Sample_Structural.rvt $C/corpus/2026/58_Snowdon_Towers_Sample_Facades.rvt $C/rosetta/2026_view_k_annotations_base.rte $C/rosetta/2026_view_l_section_schedule_var.rte; do
  b=$(basename $f | cut -c1-12); $PY tools/pdf_text_all.py $f 2>&1 | sed -n '1,/=== DETAILS/p' | python3 -c "
import sys,re
for l in sys.stdin:
    m=re.match(r'(\d+)\s.*onlyRevit\s+(\d+)\s+onlyOurs\s+(\d+)',l)
    if m: print('$b',m.group(1),'x',m.group(2),m.group(3))
" >> $out   # file view x onlyRevit onlyOurs
done
if [ "$1" = update ]; then cp $out tools/pdf_text.baseline; echo baseline updated; else
python3 - $out tools/pdf_text.baseline <<'PY'
import sys
def load(f):
    d={}
    for l in open(f):
        p=l.split()
        if len(p)>=5: d[(p[0],p[1])]=(int(p[3]),int(p[4]))
    return d
n,b=load(sys.argv[1]),load(sys.argv[2]); bad=0
for k,v in n.items():
    if k in b and (v[0]>b[k][0] or v[1]>b[k][1]): print('WORSE',k,'onlyRevit/onlyOurs',b[k],'->',v); bad+=1
print('views',len(n),'worse',bad)
PY
fi
