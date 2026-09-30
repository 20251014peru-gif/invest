#!/usr/bin/env python3
"""보고서 자동검사 (Windows·Ubuntu 공통, 모든 파일 UTF-8).
사용:
  NSK_FONT_DIR=<Noto Sans KR 폴더> python3 tools/report/test_report.py 2026-09-30        # 빌드 후 검사
  python3 tools/report/test_report.py --pdf <파일.pdf>                                    # 이미 만든 PDF만 검사 (실패하면 종료코드 1)
  python3 tools/report/test_report.py --selftest                                          # 잘못된 문구가 있으면 실제로 실패하는지 검사
검사: 10쪽, 쪽번호, 신규 4지표 값이 facts/macro_extra.json 과 일치, 필수 문구(제한판·기간자료 미제공·원문 미열람),
      과거의 잘못된 문구(수집 안 함, 원인 오기 등)가 남아 있지 않음."""
import json, os, subprocess, sys, tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# 남아 있으면 안 되는 과거 문구 (공백을 제거한 텍스트에서 찾는다)
FORBIDDEN = ['수집안함', 'CI실행시간제한', '판정가능축1/3', '하이일드OAS,CCC이하OAS</li>', '원/달러5일값(저장소1,360.0',
             '신용·펀딩은판정불가', '30년물이력은수집하지않았다']
# 반드시 있어야 하는 문구
REQUIRED = ['제한판', '기간자료수집실패로차트미제공', '기사원문·공식통계원문을열지못했다', '오래된자료']


def norm(t):
    return ''.join(t.split())


def find_violations(text, facts_items, pages):
    """(위반 목록) 을 돌려준다. 비어 있으면 통과."""
    v = []
    n = norm(text)
    for bad in FORBIDDEN:
        if bad in n:
            v.append('금지 문구 남음: ' + bad)
    for need in REQUIRED:
        if need not in n:
            v.append('필수 문구 없음: ' + need)
    for k in ('us30y', 'us_hy_oas', 'us_ccc_oas', 'sofr'):
        it = facts_items.get(k)
        if not it or it.get('value') is None:
            v.append('facts 에 값 없음: ' + k)
        elif f"{it['value']:.2f}" not in n:
            v.append(f"PDF 에 {k} 값 {it['value']:.2f} 없음")
    if len(pages) != 10:
        v.append(f'쪽수 {len(pages)} != 10')
    for i, t in enumerate(pages, 1):
        if f'{i}/10' not in norm(t):
            v.append(f'{i}쪽 쪽번호 불일치')
    return v


def load_facts():
    with open(os.path.join(ROOT, 'facts', 'macro_extra.json'), encoding='utf-8') as f:
        return {i['id']: i for i in json.load(f)['items']}


def check_pdf(path):
    import pymupdf
    d = pymupdf.open(path)
    pages = [p.get_text() for p in d]
    return find_violations(''.join(pages), load_facts(), pages)


def selftest():
    """잘못된 문구가 든 PDF 는 실제로 실패하고, 정상 문구 PDF 는 통과하는지 확인한다."""
    import pymupdf
    facts = load_facts()
    vals = ' '.join(f"{facts[k]['value']:.2f}" for k in ('us30y', 'us_hy_oas', 'us_ccc_oas', 'sofr'))
    good_head = '제한판 기간자료 수집 실패로 차트 미제공 기사 원문·공식 통계 원문을 열지 못했다 오래된 자료 ' + vals

    def make(extra):
        doc = pymupdf.open()
        for i in range(1, 11):
            pg = doc.new_page()
            body = (good_head + ' ' + extra if i == 1 else '') + f'  {i} / 10'
            pg.insert_textbox(pymupdf.Rect(30, 30, 560, 800), body, fontname='korea', fontsize=9)
        out = tempfile.mktemp(suffix='.pdf')
        doc.save(out)
        return out
    ok = make('')
    bad = make('HY OAS 수집 안 함')
    try:
        assert check_pdf(ok) == [], check_pdf(ok)
        found = check_pdf(bad)
        assert any('수집안함' in x for x in found), found
        r = subprocess.run([sys.executable, os.path.abspath(__file__), '--pdf', bad], capture_output=True, text=True, encoding='utf-8')
        assert r.returncode == 1, r.returncode  # 스크립트 종료코드도 실제로 실패
        r = subprocess.run([sys.executable, os.path.abspath(__file__), '--pdf', ok], capture_output=True, text=True, encoding='utf-8')
        assert r.returncode == 0, r.stdout + r.stderr
    finally:
        for p in (ok, bad):
            if os.path.exists(p):
                os.remove(p)
    print('OK: 잘못된 문구가 있으면 검사가 실제로 실패함 (selftest)')


def main():
    if '--selftest' in sys.argv:
        return selftest()
    if '--pdf' in sys.argv:
        path = sys.argv[sys.argv.index('--pdf') + 1]
    else:
        date = next((a for a in sys.argv[1:] if not a.startswith('--')), '2026-09-30')
        subprocess.check_call([sys.executable, os.path.join(HERE, 'build.py'), date])
        folder = os.path.join(ROOT, 'docs', 'reports', date)
        path = os.path.join(folder, sorted(f for f in os.listdir(folder) if f.endswith('.pdf'))[-1])
    bad = check_pdf(path)
    if bad:
        print('FAIL:', path)
        for b in bad:
            print(' -', b)
        sys.exit(1)
    print('OK:', path)


if __name__ == '__main__':
    main()
