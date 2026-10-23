#!/bin/bash
# h1_roofpat_ab.sh : host1 job: dxf_all with RVT_PLAN_ROOFPAT 0 and 1 (A/B of plan roof surface patterns), diff of P/R per view
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
mkdir -p out/c10
for e in 0 1; do RVT_PLAN_ROOFPAT=$e tools/dxf_all.sh out/c10/roofpat$e.tsv > /dev/null 2>&1; done
python3 - <<'PY'
def load(f):
    d={}
    for l in open(f):
        p=l.rstrip('\n').split('\t')
        if len(p)>=5: d[(p[0],p[1])]=(p[2],float(p[3]),float(p[4]))
    return d
a=load('out/c10/roofpat0.tsv'); b=load('out/c10/roofpat1.tsv')
for k in b:
    if k in a and (abs(b[k][1]-a[k][1])>0.002 or abs(b[k][2]-a[k][2])>0.002): print(k[0][:12],k[1],b[k][0][:25],'P %.3f->%.3f R %.3f->%.3f'%(a[k][1],b[k][1],a[k][2],b[k][2]))
print(len(a),len(b))
PY
echo DONE
