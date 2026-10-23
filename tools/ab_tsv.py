"""ab_tsv.py A.tsv B.tsv: views whose precision / recall differ between two compare_dxf tables (key, name, A -> B) and the mean P / R"""
import sys
def load(f):
    d = {}
    for l in open(f):
        p = l.rstrip('\n').split('\t')
        if len(p) == 5:
            try: d[(p[0], p[1])] = (p[2], float(p[3]), float(p[4]))
            except ValueError: pass
    return d
a, b = load(sys.argv[1]), load(sys.argv[2]); n = 0
for k in a:
    if k in b and (abs(a[k][1] - b[k][1]) > 5e-4 or abs(a[k][2] - b[k][2]) > 5e-4):
        n += 1; print('%-14s %-9s %-26s P %.3f -> %.3f  R %.3f -> %.3f' % (k[0][:14], k[1], a[k][0][:26], a[k][1], b[k][1], a[k][2], b[k][2]))
ks = [k for k in a if k in b]
print(len(ks), 'views,', n, 'changed; mean P %.4f -> %.4f, mean R %.4f -> %.4f' % tuple(sum(x[k][i] for k in ks) / len(ks) for x in (a, b) for i in (1, 2)) if ks else '')
