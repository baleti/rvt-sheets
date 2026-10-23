"""agg_layers.py OUT.jsonl: aggregates dxf_layers_all.sh output: per Revit layer total ink (mm), matched ink and recall over all views; per our layer ink and precision; worst (ink x miss) first"""
import sys, json, collections
rl = collections.defaultdict(lambda: [0.0, 0.0]); pl = collections.defaultdict(lambda: [0.0, 0.0]); worst = []
for l in open(sys.argv[1]):
    d = json.loads(l)
    if 'recall_by_revit_layer' not in d or d.get('recall', 1) < 0.3: continue      # sheets / 3D views whose DXF is not comparable (recall near 0) would dominate
    for k, (mm, r) in d['recall_by_revit_layer'].items(): rl[k][0] += mm; rl[k][1] += mm * r; worst.append((mm * (1 - r), d['file'][:3], d['view'], d.get('name'), k, mm, r))
    for k, (mm, p) in d['precision_by_our_layer'].items(): pl[k][0] += mm; pl[k][1] += mm * p
print('Revit layers by missed mm:')
for k, (mm, ok) in sorted(rl.items(), key=lambda kv: kv[1][1] - kv[1][0])[:25]: print('  %-18s %9.0f mm  recall %.3f  missed %8.0f' % (k, mm, ok / mm if mm else 1, mm - ok))
print('our layers:')
for k, (mm, ok) in sorted(pl.items(), key=lambda kv: kv[1][1] - kv[1][0]): print('  %-18s %9.0f mm  precision %.3f  extra %8.0f' % (k, mm, ok / mm if mm else 1, mm - ok))
print('worst (view, layer) by missed mm:')
for w in sorted(worst, reverse=True)[:25]: print('  %8.0f missed  %s %s %-32s %-16s of %7.0f recall %.3f' % w)
