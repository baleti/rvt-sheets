#!/bin/bash
# h1_noplane.sh : host1 job: dxf_all with planar wall occluders skipped (default) vs the stored baseline out/c10/plant1.tsv (same code otherwise)
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
RVT_OCC_NOPLANE=1 tools/dxf_all.sh out/c10/noplane2.tsv > /dev/null 2>&1
python3 - <<'PY'
def load(f):
    d={}
    for l in open(f):
        p=l.rstrip('\n').split('\t')
        if len(p)>=5: d[(p[0],p[1])]=(p[2],float(p[3]),float(p[4]))
    return d
a=load('out/c10/plant1.tsv'); b=load('out/c10/noplane2.tsv')
for k in b:
    if k in a and (abs(b[k][1]-a[k][1])>0.002 or abs(b[k][2]-a[k][2])>0.002): print(k[0][:12],k[1],b[k][0][:25],'P %.3f->%.3f R %.3f->%.3f'%(a[k][1],b[k][1],a[k][2],b[k][2]))
print(len(a),len(b))
PY
echo DONE
