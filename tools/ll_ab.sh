#!/bin/bash
# ll_ab.sh: RVT_LINELOAD 0/1 vs Revit DXF (P/R, layer S-LOAD-*) for the rst basic views with loads
C=~/rvt-research/corpus/2020/18_rst_basic_sample_project.rvt; G=~/rvt-research/gt_views/2020_18_rst_basic_sample_project
for e in 1; do for v in 515290 417295 245443 196649; do
  RVT_LINELOAD=$e timeout 900 python "$(dirname "$0")/compare_dxf.py" $C $v $G/$v.dxf --register 2>/dev/null | python3 -c "
import sys,json
t=sys.stdin.read(); d=json.loads(t[t.index('{'):])
l=[(k,x) for k,x in (d.get('layers') or {}).items() if 'LOAD' in k]
print('LL=$e $v P %.3f R %.3f'%(d['precision'],d['recall']), l)"
done; done
