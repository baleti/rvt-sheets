"""agg_extra.py OUT.txt [dla.jsonl]: extra_all.sh output -> ink without a Revit counterpart summed per (class, category, layer); views with overall recall < 0.3 (dla.jsonl) are skipped"""
import sys, re, json, collections
skip = set()
if len(sys.argv) > 2:
    for l in open(sys.argv[2]):
        d = json.loads(l)
        if 'view' in d and d.get('recall', 1) < 0.3: skip.add(str(d['view']))
tot = collections.defaultdict(lambda: [0.0, 0.0, 0]); cur = None
for l in open(sys.argv[1]):
    if l.startswith('##'): cur = l.split()[-1]; continue
    if cur in skip: continue
    m = re.match(r"\((\d+), '(\w+)'\) extra mm (\d+) of (\d+) (\w+) (-?\d+) ?(.*?) \(", l) or re.match(r"\((\d+), '(\w+)'\) extra mm (\d+) of (\d+) (\w+) (-?\d+)", l)
    if not m: continue
    k = (m.group(5), m.group(6), m.group(2)); tot[k][0] += float(m.group(3)); tot[k][1] += float(m.group(4)); tot[k][2] += 1
for k, (ex, all_, n) in sorted(tot.items(), key=lambda kv: -kv[1][0])[:30]: print('%-22s cat %-9s %-11s extra %8.0f mm of %8.0f  (%d elems)' % (k[0], k[1], k[2], ex, all_, n))
