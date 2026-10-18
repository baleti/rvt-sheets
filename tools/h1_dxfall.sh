#!/bin/bash
# h1_dxfall.sh : host1 job: snowdon_l2_check + 87-view dxf_all sweep (annot tree) compared with the previous sweep
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
python tools/snowdon_l2_check.py 2>&1 | tail -1
tools/dxf_all.sh out/annot/dxf_all11.tsv > /dev/null 2>&1
python3 - <<'PY'
def load(f):
    d={}
    for l in open(f):
        p=l.rstrip('\n').split('\t')
        if len(p)>=5:
            try: d[(p[0],p[1])]=(p[2],float(p[3]),float(p[4]))
            except: pass
    return d
a=load('out/annot/dxf_all10.tsv'); b=load('out/annot/dxf_all11.tsv')
for k in b:
    if k in a and (abs(b[k][1]-a[k][1])>0.004 or abs(b[k][2]-a[k][2])>0.004): print(k[0][:12],k[1],b[k][0][:25],'P %.3f->%.3f R %.3f->%.3f'%(a[k][1],b[k][1],a[k][2],b[k][2]))
print(len(a),len(b))
PY
echo DONE
