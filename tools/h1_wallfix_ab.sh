#!/bin/bash
# h1_wallfix_ab.sh : host1 job: dxf_all sweep with RVT_WALL_MESHFIX=0 vs 1 (same tree), prints views whose precision/recall changed
cd "$(dirname "$0")/.."; export PATH=$HOME/rvt-env/bin:$PATH; mkdir -p out/vg
RVT_WALL_MESHFIX=0 tools/dxf_all.sh out/vg/dxf_off.tsv > /dev/null 2>&1
RVT_WALL_MESHFIX=1 tools/dxf_all.sh out/vg/dxf_on.tsv > /dev/null 2>&1
python3 - <<'PY'
def load(f):
    d={}
    for l in open(f):
        p=l.rstrip('\n').split('\t')
        if len(p)>=5:
            try: d[(p[0],p[1])]=(p[2],float(p[3]),float(p[4]))
            except ValueError: pass
    return d
a=load('out/vg/dxf_off.tsv'); b=load('out/vg/dxf_on.tsv'); n=0
for k in sorted(a):
    if k in b and (abs(a[k][1]-b[k][1])>0.002 or abs(a[k][2]-b[k][2])>0.002): print('CHANGED',k,a[k],'->',b[k]); n+=1
print('views',len(a),'changed',n, 'mean P off %.4f on %.4f' % (sum(x[1] for x in a.values())/max(len(a),1), sum(b[k][1] for k in a if k in b)/max(len(a),1)))
PY
