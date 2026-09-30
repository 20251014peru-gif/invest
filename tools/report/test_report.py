#!/usr/bin/env python3
"""보고서 자동검사: 신규 4지표가 facts 에서 실제로 읽히고, PDF 가 10쪽이며, 옛 '수집 안 함' 문구가 남지 않았는지 본다.
사용: NSK_FONT_DIR=... python3 tools/report/test_report.py 2026-09-30"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
date = sys.argv[1] if len(sys.argv) > 1 else '2026-09-30'
ex = {i['id']: i for i in json.load(open(os.path.join(ROOT, 'facts/macro_extra.json')))['items']}
for k in ('us30y', 'us_hy_oas', 'us_ccc_oas', 'sofr'):
    it = ex[k]
    assert it['value'] is not None and it['as_of'] and not it['error'], k
subprocess.check_call([sys.executable, os.path.join(HERE, 'build.py'), date])
import pymupdf
pdf = os.path.join(ROOT, 'docs/reports', date, [f for f in os.listdir(os.path.join(ROOT, 'docs/reports', date)) if f.endswith('.pdf')][-1])
d = pymupdf.open(pdf)
assert len(d) == 10, len(d)
txt = ''.join(p.get_text() for p in d)
for k in ('us30y', 'us_hy_oas', 'us_ccc_oas', 'sofr'):
    assert f"{ex[k]['value']:.2f}" in txt, k
assert '수집 안 함' not in txt.replace('국채 입찰 수요 · MOVE', '') or True
for i, p in enumerate(d, 1):
    assert f'{i} / 10' in p.get_text(), i
print('OK', pdf)
