cd ~/src/rvt-sheets-annot; python tools/pdf_text_all.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 582458 > ~/h1_582458.txt 2>&1
python - <<'PY' >> ~/h1_582458.txt 2>&1
import sys, os
sys.path.insert(0, os.path.expanduser('~/src/rvt-sheets-annot'))
from rvtsheets.decode import Decoder
from rvtsheets.reader import ob
dec = Decoder(os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt')); f = dec.f
for r in f.recs('UnitsElem'):
    u = ob(r['fields'].get('m_units')) or {}
    for e in u.get('m_formatOptionsMap') or []:
        e = ob(e); k = (ob(e.get('first')) or {}).get('m_typeId', '')
        if 'area' in k: print('AREAFMT', k, {a: b for a, b in ob(e['second']).items() if not isinstance(b, (dict, list))})
PY
python tools/area_probe.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt >> ~/h1_582458.txt 2>&1
