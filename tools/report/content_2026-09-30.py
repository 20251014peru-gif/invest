"""2026-09-30 (수) 07:00 KST 판 내용. 다음 날 보고서는 이 파일을 복사해 날짜와 값·문장을 새로 확인해 바꾼다.
구조와 검증법만 이어받고 숫자와 이슈 상태를 그대로 복사하지 않는다 (docs/REPORT_PLAYBOOK.md)."""
import json
import datetime as dt
import os
from lib import (esc, badge, sign_txt, line_chart, index100, page, NAVY, ORANGE, RED, BLUE, TEAL, GRAY, MUTED)

DATE = '2026-09-30'
DATE_TXT = '2026.09.30 (수) 07:00 KST'
VER = 'v1.1'
TITLE = '시장 톱니바퀴 아침보고서 (제한판)'
FOOT = '정보 기준 07:00 KST (07시 이후 발표분은 별도 표기) · 검증 수준: 원문 미열람, 검색 요약과 저장소 값'
TOTAL = 10

OVERRIDES = {  # 저장소 값이 마감가와 어긋난 곳을 검색으로 확인된 마감가로 바로잡은 것 (등급 ○, 5.3.3 참조)
    '2026-09-29': {'sp500': 7683.69, 'nasdaq': 26820.38, 'sox': 12465.24, 'vix': 16.07},
    '2026-09-30': {'sp500': 7670.84, 'nasdaq': 26797.54, 'sox': 12629.16, 'vix': 16.04, 'kospi': 6870.81, 'kosdaq': 849.80},
}


def _rows(root):
    h = json.load(open(os.path.join(root, 'facts/macro_history.json'), encoding='utf-8'))['days']
    keys = [k for k in sorted(h) if dt.date.fromisoformat(k).weekday() in (1, 2, 3, 4, 5)]
    return h, keys


def _series(h, keys, key):
    out = []
    for k in keys:
        v = OVERRIDES.get(k, {}).get(key, h[k].get(key))
        out.append(v)
    return out


def _lab(k):
    d = dt.date.fromisoformat(k)
    return f'{d.month}/{d.day}'


def _extra(root):
    """facts/macro_extra.json 의 항목을 id 로 돌려준다. 값·직전값·관측일·신선도·오류를 그대로 쓴다 (결측을 채우지 않는다)."""
    d = json.load(open(os.path.join(root, 'facts/macro_extra.json'), encoding='utf-8'))
    return {i['id']: i for i in d['items']}, d.get('collected_at', '')


def _fx(it, dec=2, unit=None):
    """(값문자열, 변화문자열, 관측일, 상태) — 오류·stale·결측은 정상값처럼 쓰지 않는다."""
    if not it or it.get('value') is None or it.get('error'):
        return ('미수집', '—', '—', 'gray')
    u = unit if unit is not None else it.get('unit', '')
    v = f"{it['value']:.{dec}f}{u}"
    ch = it.get('change')
    chs = '—' if ch is None else f"{ch:+.{dec}f}{u.replace('%p', '%p')} " + (('확대' if '%p' in u else '상승') if ch > 0 else ('축소' if '%p' in u else '하락') if ch < 0 else '변화 없음')
    return (v, chs, it.get('as_of', '—'), 'orange' if it.get('freshness') == 'stale' else 'teal')


def _status(root):
    ex, ex_at = _extra(root)
    return f"""<div class="tight" style="margin-top:2mm"><b>데이터 상태표</b>
<table><tr><th>항목</th><th>상태</th><th>근거</th></tr>
<tr><td>최신값 수집 (macro_extra.json)</td><td>{badge('정상', 'teal')}</td><td>8/8 성공, 수집 {esc(ex_at[:16].replace('T', ' '))} KST</td></tr>
<tr><td>기간 시계열 (macro_periods.json)</td><td>{badge('오래된 자료', 'orange')}</td><td>기존 14개 시리즈의 마지막 점 9/10, 수집일 9/13. 최근 실행은 전 시리즈 시간 초과</td></tr>
<tr><td>신규 4개 시계열</td><td>{badge('없음', 'red')}</td><td>macro_periods.json에 항목 없음</td></tr>
<tr><td>원인</td><td>{badge('요청 시간초과', 'gray')}</td><td>최근 실행 18개 시리즈 전부 FRED 읽기 시간초과(TimeoutError). 워크플로 전체 시간 제한이 아니라 요청 단위. 수집기는 별도 수정 대상</td></tr></table></div>"""


def _ledger(root):
    return json.load(open(os.path.join(root, 'analysis/issue_ledger.json'), encoding='utf-8'))


# ---------------------------------------------------------------- pages
def p1():
    lead = """<div class="lead">금리와 AI 우려의 <b>흐름은 이어졌고</b>, 반대급부가 작동하기 시작한 곳은 <b>유가뿐</b>이다.
AI는 심리·가격 쪽 반대급부(우려)만 작동했고 실물(주문·HBM 가격·capex)은 아직이다.
한국은 반도체에 수출과 지수가 함께 걸려 있어 <b>마이크론 실적(미국 9/30)과 10/1 수출</b>이 첫 시험대다.
<div class="s">위험단계 <b>2단계 경계</b> (주가 축 판정, 신용·펀딩 축은 FRED 공식값이 들어왔으나 임계값·레포·발행 자료 없음) · 제한판: 기사 원문 미열람 · 오늘 밤 21:30 미 PCE</div></div>"""
    cards = f"""<div class="grid4">
<div class="card bar-l"><div class="k">G1 금리·연준 {badge('유지 · ③가격반영','orange')}</div>
<div class="h">미 30년 5.61% 상승, 20년 최고</div>
<div class="v">10년 5.282% 상승(+4bp). 연준 9/16 +25bp로 3.75~4.00%, 윌리엄스 &quot;서두를 필요 없다&quot;(○)</div>
<div class="n">다음: 21:30 PCE 예상 3.7% / 근원 3.3%</div></div>
<div class="card bar-l"><div class="k">G2 유가·중동 {badge('반대급부 초기 작동','teal')}</div>
<div class="h">WTI 89.38달러 하락(−3.5%)</div>
<div class="v">Brent 102.59달러 하락(−2.6%). 사우디 수출 약 600만 b/d(○). 미국의 이란 답변 대기</div>
<div class="n">다음: 이란 답변, 23:30 EIA 재고</div></div>
<div class="card bar-l"><div class="k">G3·G8 AI·반도체 {badge('심리 작동 · 실물 미작동','blue')}</div>
<div class="h">OpenAI 출시 취소·훈련 중단(9/28, ○)</div>
<div class="v">SOX 9/29 +1.31% 상승. HBM 스팟이 계약가의 4~5배(○*). 실물 하향 근거 없음</div>
<div class="n">다음: 마이크론 FQ4 실적(미국 9/30)</div></div>
<div class="card bar-l"><div class="k">G5·G4 한국 {badge('매도 지속 · 낙폭 축소','red')}</div>
<div class="h">KOSPI 6,870.81 하락(−0.27%)</div>
<div class="v">외국인 약 −2.90조원 순매도, 개인 +1.15조원 순매수. 8월 생산 −1.3% 감소(07시 이후, 일회성 요인 보도)</div>
<div class="n">다음: 10/1 9월 수출 확정치</div></div></div>"""
    kr = """<h2>한국에 도착한 충격</h2>
<div class="grid3">
<div class="card soft"><div class="k">수출 구조 (9/1~20, 관세청 잠정 ○)</div><div class="h">반도체 341억달러, 수출의 47.8%</div><div class="v">전년 대비 +259.4% 증가. 반도체 제외 수출도 증가(9/1~10 기준 +25.8%)</div></div>
<div class="card soft"><div class="k">지수 위치 (검색 요약 ○)</div><div class="h">KOSPI, 6/19 최고 종가 대비 약 −24% 하락</div><div class="v">최고 종가 9,063.84 → 6,870.81. 삼성전자+SK하이닉스 시총 비중 52% 초과(6/3 제목)</div></div>
<div class="card soft"><div class="k">수급 (9/1 보도 ○)</div><div class="h">외국인 올해 누적 순매도 약 170조원</div><div class="v">월간 순매수는 8개월 중 2개월. 오늘 매도는 새 충격이 아니라 추세의 연장선일 수 있음(추정)</div></div></div>"""
    flow = f"""<h2>오늘 시장을 움직이는 톱니 흐름도</h2>
<div class="chain">
<div class="node teal"><div class="a">전쟁·호르무즈</div><div class="b">협상 진행, 제안 거부(9/27~28)</div></div><div class="arw">→</div>
<div class="node teal"><div class="a">유가 하락</div><div class="b">WTI −3.5%</div></div><div class="arw warn">⇢</div>
<div class="node orange"><div class="a">장기금리 상승</div><div class="b">10년 +4bp · 30년 +4.7bp</div></div><div class="arw">→</div>
<div class="node red"><div class="a">외국인 매도</div><div class="b">약 −2.90조원</div></div><div class="arw">→</div>
<div class="node red"><div class="a">KOSPI 하락</div><div class="b">−0.27%</div></div></div>
<div class="small" style="margin:-0.6mm 0 1.4mm">점선 화살표(⇢)는 오늘 방향이 어긋난 이음매다: 유가는 내렸는데 장기금리는 올랐다 (추정, 신뢰도 ○).</div>
<div class="chain">
<div class="node blue"><div class="a">AI 우려 확산</div><div class="b">9/14 → 9/28 출시 취소</div></div><div class="arw">→</div>
<div class="node blue"><div class="a">SOX 변동</div><div class="b">9/28 −1.6%(△) · 9/29 +1.31%</div></div><div class="arw">→</div>
<div class="node red"><div class="a">외국인 반도체 매도</div><div class="b">2일 약 6.1조원, 87% 반도체(○)</div></div><div class="arw warn">⇢</div>
<div class="node gray"><div class="a">수출·주문 (실물)</div><div class="b">반도체 수출 +259.4% 증가</div></div></div>"""
    risk = """<h2>현재 위험단계와 행동 조건</h2>
<div class="gauge"><div>1 안정</div><div class="on">2 경계 (현재)</div><div class="na">3 압박</div><div class="na">4 강제매도</div></div>
<div class="grid2">
<div class="card"><div class="h">축별 판정: 주가 ○ · 신용 부분 · 펀딩 부분</div><div class="v">주가 축은 S&amp;P −0.16%, 나스닥 −0.09%, VIX 16.04로 경계 수준. 신용은 HY OAS 3.02%p(+0.09), CCC 11.46%p(+0.18)로 <b>확대 방향</b>이나 수준을 가를 달님 임계값이 없다. SOFR 3.90%는 변화 없음. 레포·발행·MOVE는 미수집(안정으로 읽지 않음). 관측일 9/28(FRED, 공식).</div></div>
<div class="card"><div class="h">행동 규칙 5개: 충족 0 · 미충족 2 · 미확인 3</div><div class="v">임계값은 달님이 확정한 것만 규칙으로 쓴다. 오늘 표시는 GPT 지침서 예시값을 임시로 쓴 것이다(9쪽).</div></div></div>"""
    return f'<h1>Executive Dashboard</h1><div class="sub">오늘의 한 문장 결론, 핵심 이슈, 한국 충격, 톱니 흐름도, 위험단계</div>{lead}{cards}{kr}{flow}{risk}'


def p2(root):
    rows = [
        ('미 10년 금리', '5.24% (9/28, FRED)', '5.282% (9/29 종가, AP)', '+4bp 상승', '장기금리 부담 강화', ('강화', 'orange'), '○'),
        ('미 30년 금리', '5.56% (9/28)', '5.61% (9/29)', '+4.7bp 상승', '2004년 이후 최고 수준으로 보도', ('강화', 'orange'), '○'),
        ('미 2년 금리', '4.81% (9/25)', '4.92% (9/28)', '+11bp 상승', '10월 인상 기대는 줄고 연내 1회 반영(윌리엄스). 9/29 종가 ✕', ('유지', 'blue'), '○'),
        ('WTI (결제가)', '92.60달러 (9/28)', '89.38달러 (9/29)', '−3.22달러, −3.5% 하락', '반대급부 초기 작동. 월간으로는 상승', ('반대급부 후보', 'teal'), '◎'),
        ('Brent (결제가)', '105.28달러 (9/28)', '102.59달러 (9/29)', '−2.69달러, −2.6% 하락', '100달러대 유지. AP는 96.16달러 보도(계약월 차이 미해소)', ('유지', 'blue'), '○'),
        ('S&P 500', '7,683.69 (9/28)', '7,670.84 (9/29)', '−0.16% 하락', '금리 상승에 약보합', ('유지', 'blue'), '◎'),
        ('나스닥', '26,820.38', '26,797.54', '−0.09% 하락', '낙폭 제한', ('유지', 'blue'), '◎'),
        ('SOX 반도체', '12,465.24 (9/28)', '12,629.16 (9/29)', '+1.31% 상승', '9/28 값이 저장소 안에서 12,696과 충돌', ('반등 1일', 'orange'), '△'),
        ('VIX', '16.07 (9/28)', '16.04 (9/29)', '−0.03 소폭 하락', '평온. 신용·펀딩 자료 없음', ('유지', 'blue'), '○'),
        ('KOSPI', '6,889.74 (9/28)', '6,870.81 (9/29)', '−18.93p, −0.27% 하락', '9/28 −2.70%에 이어 낙폭 축소', ('유지', 'blue'), '◎'),
        ('KOSDAQ', '846.58', '849.80', '+0.38% 상승', 'KOSPI 대비 상대 강세', ('신규 관측', 'teal'), '◎'),
        ('외국인 KOSPI 순매수', '−3.23조원 (9/28)', '−2.90조원 (9/29)', '순매도 지속, 규모 0.33조원 축소', '개인 +1.15조원 순매수가 흡수. GPT는 3.08조원(△)', ('유지', 'blue'), '○'),
        ('국고채 10년', '4.539% (9/28)', '4.476% (9/29)', '−6.3bp 하락', '미 장기금리 상승과 반대 방향', ('불일치', 'orange'), '◎'),
        ('원/달러 (ECOS 매매기준율)', '— (9/28 값 미대조)', '1,360.0 (9/29, 한국은행 ECOS)', '전일 비교 미대조', '검색 1,357.60·GPT 1,356.7은 시장 종가로 정의·시각이 달라 합치지 않음. 9/30 매매기준율 1,358.4는 07시 이후', ('정의 차이', 'gray'), '○'),
    ]
    trs = ''.join(f'<tr><td><b>{esc(a)}</b></td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td><td>{esc(e)}</td><td>{badge(*f)}</td><td class="num">{esc(g)}</td></tr>' for a, b, c, d, e, f, g in rows)
    diff = f"""<h2>오늘 가장 중요한 방향 불일치 3개 <span class="small">(신뢰도 C 가설로 표시, 다음 자료로 검증)</span></h2>
<div class="grid3">
<div class="card bar-l"><div class="h">① 유가 하락인데 미 장기금리 상승</div><div class="v">WTI −3.5% 하락, 10년 +4bp·30년 +4.7bp 상승. 유가 외의 힘(기간 프리미엄, 인플레 기대, 연준 경로, 국채 수급)이 장기금리를 밀 가능성 <span class="tag t-orange">가설</span></div><div class="n">검증: 21:30 PCE 뒤 30년물, 이란 답변 뒤 유가와 금리의 동조</div></div>
<div class="card bar-l"><div class="h">② 미 반도체 반등인데 한국 외국인 반도체 매도</div><div class="v">SOX +1.31% 상승, 외국인 2일 약 6.1조원 순매도(87%가 반도체, 단일 요약 ○). AI 우려, 분기말 리밸런싱, 금리 중 무엇인지 가를 수 없음 <span class="tag t-orange">가설</span></div><div class="n">검증: KRX 투자자별·업종별 원자료, 마이크론 후 10/1 수급</div></div>
<div class="card bar-l"><div class="h">③ 미 금리 상승인데 국고채 금리 하락</div><div class="v">국고 10년 −6.3bp 하락. 한은은 8/27 3.00%로 두 달 연속 인상(성장·물가·주택 사유 보도 ○)해 미국을 따라가지 않음 <span class="tag t-orange">가설</span></div><div class="n">검증: 한은 10월 금통위(날짜 ✕), 외국인 채권 수급</div></div></div>"""
    return f"""<h1>Change Board</h1><div class="sub">이전 값, 최신 값, 변화, 해석. 상승·하락은 부호와 문자를 함께 적었다 (등급: ◎ 2곳 이상 일치, ○ 검색 요약, △ 충돌)</div>
<table><tr><th>지표</th><th>이전</th><th>최신</th><th>변화</th><th>해석</th><th>상태</th><th class="num">등급</th></tr>{trs}</table>{diff}{_status(root)}"""


def p3(root):
    h, keys = _rows(root)
    tags = iter([
        '마지막 관측: 2년·10년 FRED 9/28, 종가(AP 검색) 9/29 · 수집일: 저장소 스냅샷 9/30 · 원천: macro_history.json (macro_periods.json 아님)',
        '마지막 관측: 9/29 마감 · 수집일: 저장소 스냅샷 9/30 · 원천: macro_history.json',
        '마지막 관측: 9/29 마감 · 수집일: 저장소 스냅샷 9/30 · 원천: macro_history.json',
        '마지막 관측: 9/29 마감 · 수집일: 저장소 스냅샷 9/30 · 원천: macro_history.json',
        '마지막 관측: 9/29 결제가(검색), 9/30 07시 호가 · 수집일: 검색 9/30 · 원천: 저장소 아님',
    ])

    def lc(*a, **k):
        k['h'] = 150
        k['note'] = (k.get('note') or '') + ' ▶ ' + next(tags)
        return line_chart(*a, **k)
    cats = [_lab(k) for k in keys]
    n = len(cats)
    y2 = _series(h, keys, 'us2y')
    y10 = _series(h, keys, 'us10y')
    ap = [None] * n
    ap[-1] = 5.282
    c1 = lc(cats, [
        {'name': '10년', 'color': NAVY, 'vals': y10},
        {'name': '2년', 'color': BLUE, 'vals': y2},
        {'name': '', 'color': ORANGE, 'vals': ap, 'hollow_last': True, 'width': 0.1},
    ], '미 국채 2년·10년 (%)', hlines=[(5.30, '', RED)], note='FRED 값은 2영업일 늦게 반영되어 마지막 점은 9/28 관측이다. 속이 빈 점은 9/29 종가(AP 검색 요약). 30년물 기간자료는 수집 실패로 이 차트에 없다. 점선 5.30%는 GPT 지침서의 4단계 후보 예시값으로 달님 확정 전이다.', xtick_every=3)
    c2 = lc(cats, [{'name': 'VIX', 'color': ORANGE, 'vals': _series(h, keys, 'vix')}], 'VIX', note='수집일 아침(KST)에 기록된 직전 마감. 9/29·9/30 두 점은 검색으로 확인한 마감가로 바로잡았다.', xtick_every=3, fmt='{:.1f}')
    nas = index100(_series(h, keys, 'nasdaq'))
    sox = index100(_series(h, keys, 'sox'))
    c3 = lc(cats, [
        {'name': '나스닥', 'color': NAVY, 'vals': nas},
        {'name': 'SOX', 'color': BLUE, 'vals': sox},
    ], '나스닥·SOX (9/3 마감=100)', fmt='{:.0f}', note='서로 단위가 달라 첫 관측일을 100으로 맞춘 지수화 값. SOX 9/28은 12,465.24(전일값 필드) 기준, 저장소 이력 행(12,696)과 충돌해 △.', xtick_every=3)
    kkeys = [k for k in keys if (OVERRIDES.get(k, {}).get('kospi') or h[k].get('kospi')) is not None]
    kc = [_lab(k) for k in kkeys]
    ks = index100([OVERRIDES.get(k, {}).get('kospi', h[k].get('kospi')) for k in kkeys])
    kd = index100([OVERRIDES.get(k, {}).get('kosdaq', h[k].get('kosdaq')) for k in kkeys])
    c4 = lc(kc, [
        {'name': 'KOSPI', 'color': NAVY, 'vals': ks},
        {'name': 'KOSDAQ', 'color': TEAL, 'vals': kd},
    ], 'KOSPI·KOSDAQ (9/7 마감=100)', fmt='{:.1f}', note='9/24~25 추석 휴장으로 같은 값이 이어진다. 9/30 점은 9/29 종가(검색 ◎). KOSDAQ이 KOSPI보다 상대 강세.', xtick_every=2)
    c5 = lc(['9/24', '9/25', '9/28', '9/29', '9/30'], [
        {'name': 'Brent', 'color': NAVY, 'vals': [106.60, 104.32, 105.28, 102.59, None]},
        {'name': 'WTI', 'color': TEAL, 'vals': [94.61, 92.41, 92.60, 89.38, 89.31], 'hollow_last': True},
    ], 'WTI·Brent 결제가 (달러)', fmt='{:.1f}', xtick_every=1, note='5거래일뿐이며 20일 결제가 이력은 없다. 9/24는 9/25 하락폭에서 역산, 9/30 WTI는 07시 호가(속이 빈 점). 저장소의 WTI 이력은 호가라 섞지 않았다.')
    ex, ex_at = _extra(root)
    per = json.load(open(os.path.join(root, 'facts/macro_periods.json'), encoding='utf-8'))['items']
    rows = ''
    for iid, nm in (('us30y', '미 국채 30년'), ('us_hy_oas', '하이일드 OAS'), ('us_ccc_oas', 'CCC 이하 OAS'), ('sofr', 'SOFR')):
        it = ex.get(iid)
        v, ch, asof, col = _fx(it)
        prev = '—' if not it or it.get('prev') is None else f"{it['prev']:.2f}"
        ser = '차트 가능' if iid in per else '시계열 미적재'
        rows += f"<tr><td><b>{nm}</b></td><td class='num'>{v}</td><td class='num'>{prev}{(it or {}).get('unit', '')}</td><td>{ch}</td><td>{asof}<br><span class='small'>경과 {it.get('age_days', '—') if it else '—'}일 · {esc(it.get('freshness', '—') if it else '—')}</span></td><td class='num'>{esc(it.get('access_status', '—') if it else '—')}</td><td>{ser}</td></tr>"
    newtbl = f"""<div class="tight" style="margin-top:3mm"><b>신규 수집 4지표 (FRED 공식, facts/macro_extra.json · 수집 {esc(ex_at[:16].replace('T', ' '))} KST)</b>
<table><tr><th>지표</th><th class="num">최신</th><th class="num">직전</th><th>변화</th><th>관측일</th><th class="num">접근</th><th>기간 차트</th></tr>{rows}</table>
<div class="small">신규 4지표: <b>기간자료 수집 실패로 차트 미제공</b>. 관측일 9/28은 FRED 발표 지연이다.</div></div>"""
    gap = """<div class="gap"><b>데이터 공백 패널 — 아직 수집하지 않은 지표</b> (안정으로 읽지 않는다)
<ul style="margin-top:1mm">
<li>레포시장, MOVE(국채 변동성), 국채 입찰 수요</li>
<li>WTI·Brent 20일 결제가 (계약월별)</li>
<li>외국인·기관·개인 수급 원자료(KRX), 방어 섹터·사이버보안 지수</li></ul></div>"""
    return f"""<h1>Actual Data Charts</h1><div class="sub">저장소 이력에서 얻은 최근 {n}개 수집일 시계열. x축은 수집일(KST 아침), 값은 직전 마감 또는 공식 발표 최신 관측이다. 20거래일 이력이 없는 지표는 아래 공백 패널에 적었다.</div>
<div class="grid2">{c1}{c2}{c3}{c4}{c5}{gap}</div>{newtbl}"""


def p4():
    def ch(nodes):
        parts = []
        for i, (a, b, col) in enumerate(nodes):
            parts.append(f'<div class="node {col}"><div class="a">{a}</div><div class="b">{b}</div></div>')
            if i < len(nodes) - 1:
                parts.append('<div class="arw">→</div>')
        return '<div class="chain">' + ''.join(parts) + '</div>'
    ca = ch([('전쟁·호르무즈', '협상 진행, 7일 휴전 제안 거부', 'gray'), ('공급·운임', '사우디 수출 약 600만 b/d(○)', 'teal'), ('유가·물가', 'WTI −3.5% · 유로 물가 3.3%', 'teal'), ('연준·ECB·BOJ', '3곳 모두 25bp 인상', 'orange'), ('한국 성장주·항공·화학', '매핑 근거 약함, 관찰', 'gray')])
    cb = ch([('연준 9/16 인상', '3.75~4.00%, 12–0', 'orange'), ('미 30년 5.61%', '20년 최고 · 10년 5.282%', 'orange'), ('달러·외국인', 'DXY 101.4 · 외국인 −2.90조원', 'red'), ('KOSPI', '−0.27% · 최고 대비 약 −24%', 'red'), ('한은 3.00%', '자국 사유로 인상, 국고채 하락', 'blue')])
    cc = ch([('OpenAI 출시 취소', '9/28 훈련 중단(WSJ 인용 ○)', 'blue'), ('SOX·나스닥', '9/28 −1.6%(△) · 9/29 +1.31%', 'blue'), ('한국 반도체 수급', '외국인 매도, 개인·기관 흡수', 'red'), ('삼성전자·SK하이닉스', '9/28 −5.25% · −4.83%', 'red'), ('반도체 수출 (실물)', '+259.4% · 비중 47.8%', 'teal')])
    seams = [
        ('유가 → 장기금리', '유가 −3.5% 하락, 10년 +4bp·30년 +4.7bp 상승', '불일치', 'orange', '○', '21:30 PCE 뒤 30년물, 이란 답변 뒤 유가와 금리'),
        ('장기금리 → 나스닥', '금리 상승, 나스닥 −0.09% 하락', '부분 일치', 'blue', '◎', '30년 5.61% 이후 지수의 낙폭 확대 여부'),
        ('미 금리 → 국고채', '미 10년 상승, 국고 10년 −6.3bp 하락', '불일치', 'orange', '◎', '한은 10월 금통위(날짜 ✕)'),
        ('외국인 매도 → 원화', '외국인 −2.90조원 순매도, 원화 방향 출처 충돌', '판정 불가', 'gray', '△', 'ECOS 종가, KRX 수급'),
        ('AI 우려 → 반도체 주가', '9/28 SOX −1.6%(△), 9/29 +1.31% 반등', '반응 후 반등', 'blue', '○', '마이크론 실적(미국 9/30)'),
        ('반도체 주가 → 한국 수출', '주가 변동에도 수출 +259.4%, 비중 47.8%', '불일치 (실물 유지)', 'orange', '○', '10/1 9월 수출 확정치'),
        ('AI 우려 → 한국 수급', '외국인 반도체 중심 매도(87%, 단일 요약 ○)', '일치 (주체 교체)', 'blue', '○', 'KRX 투자자별 원자료'),
    ]
    trs = ''.join(f'<tr><td><b>{a}</b></td><td>{b}</td><td>{badge(c, d)}</td><td class="num">{e}</td><td>{f}</td></tr>' for a, b, c, d, e, f in seams)
    return f"""<h1>World-to-Korea Transmission</h1><div class="sub">사건 → 중간 변수 → 시장가격 → 기업 실적 → 한국 수급과 산업. 각 이음매의 방향을 숫자로 확인한다. 회색 점선 칸은 근거가 약하거나 미확인이다.</div>
<h2>경로 A. 에너지·전쟁 → 물가·금리 → 한국</h2>{ca}
<h2>경로 B. 미 금리·달러 → 외국인 수급 → 한국 지수</h2>{cb}
<h2>경로 C. AI 우려 → 반도체 → 한국 수출·수급</h2>{cc}
<h2>이음매 점검표</h2>
<table><tr><th>이음매</th><th>관측</th><th>방향</th><th class="num">신뢰도</th><th>다음 검증자료</th></tr>{trs}</table>
<div class="warnbox"><b>방향 불일치 해석 (C 가설).</b> 유가는 내렸는데 장기금리가 올랐다면 장기금리를 미는 힘이 유가 외에도 있다는 뜻일 수 있다. 반도체는 주가와 외국인 수급이 흔들리는데 수출은 사상 최대라면 시장은 심리·수급 쪽에서 반대급부를 먼저 가격에 넣고 실물은 아직 확인하지 않은 상태일 수 있다. 어느 쪽도 인과로 확정하지 않으며 위 검증자료가 나올 때까지 가설로 둔다.</div>"""


STAGES = ['점화', '확산', '가격반영', '포화', '반대급부', '소멸', '재점화']


def p5(root):
    L = _ledger(root)
    today = dt.date(2026, 9, 30)
    rows = ''
    life = '<div class="life"><div class="c hd n">이슈</div>' + ''.join(f'<div class="c hd">{i + 1} {s}</div>' for i, s in enumerate(STAGES))
    for it in L['issues']:
        fs = it.get('first_seen')
        days = (today - dt.date.fromisoformat(fs)).days + 1 if fs else None
        span = f"{fs[5:].replace('-', '/')} → {it['last_confirmed'][5:].replace('-', '/')}" if fs else '시작일 ✕ → ' + it['last_confirmed'][5:].replace('-', '/')
        dtxt = f'{days}일' if days else '—'
        rows += f"<tr><td><b>{it['id']}</b> {esc(it['name'])}</td><td style='white-space:nowrap'>{span}<br><span class='small'>{dtxt} · {it['repeat_count']}건</span></td><td>{esc(STAGES[it['stage'] - 1]) if it['stage'] else '미점등'}</td><td>{esc(it['direction'])}</td><td>{esc(it['counter_condition'])}</td><td>{esc(it['refutation'])}</td><td class='num'>{esc(it['confidence'])}</td></tr>"
        life += f"<div class='c n'>{it['id']} {esc(it['name'].split('·')[0].split(' ')[0][:9])}</div>"
        for i in range(1, 8):
            cell = ''
            if it['stage'] == i:
                cell = '<span class="dot" style="background:#0F2A4A"></span>'
            if it['id'] == 'G2' and i == 3:
                cell = '<span class="dot" style="background:#D9730D"></span>'
            if it['id'] == 'G6' and i == 1:
                cell = '<span class="dot" style="border:1pt dashed #8A93A3"></span>'
            life += f'<div class="c">{cell}</div>'
    life += '</div>'
    return f"""<h1>Issue Ledger</h1><div class="sub">기준 파일: <b>analysis/issue_ledger.json</b>. 오늘이 이 장부의 첫 기록일이라 전일 비교는 없다. 내일부터 ID와 상태를 이어받는다.</div>
<h2>수명주기 위치</h2>{life}
<div class="note" style="margin-top:1mm">● 남색 = 현재 단계, ● 주황 = G2 전달 톱니의 단계(원인은 5 반대급부), 점선 원 = G6 미점등. 단계는 점화 → 확산 → 가격반영 → 포화 → 반대급부 → 소멸 → 재점화. 소멸은 세 조건(원인 반전 · 반대급부 실이행 · 가격 둔감화)이 함께 확인될 때만 판정하며 오늘 소멸로 판정한 이슈는 없다.</div>
<h2>이슈 장부</h2>
<div class="tight"><table><tr><th>ID · 이슈</th><th>최초 → 최근</th><th>단계</th><th>방향</th><th>반대급부 조건</th><th>반증 조건</th><th class="num">신뢰도</th></tr>{rows}</table></div>
<div class="warnbox"><b>최초 발생일은 “이 장부에서 확인된 최초 근거일”이다.</b> 실제 발생은 더 이를 수 있다(G2는 약 7개월, 시작일 미확인).</div>"""


def p6():
    tbl = """<table><tr><th>구분</th><th>내용</th><th>판정</th></tr>
<tr><td>협상</td><td>미·이란 뉴욕 간접협상(카타르 중재). 이란은 &quot;지금은 호르무즈만 다룬다&quot;고 발언 (○)</td><td>진행 중, 합의 아님</td></tr>
<tr><td>제안</td><td>이란 7개항 제안, 미국 답변 대기. 트럼프는 7일 휴전·호르무즈 재개방 제안을 거부(9/27~28) (○)</td><td>결렬 발언 후 재협상</td></tr>
<tr><td>실물</td><td>사우디 수출 9월 약 600만 b/d(전쟁 후 최고), 호르무즈 경유분 9월 첫 2주 200만 b/d 이상 (CNBC 9/25 ○)</td><td>회복 시작, 재개방 아님</td></tr>
<tr><td>공급 제안</td><td>전략비축유 4,000만 배럴 제안 (GPT 인용)</td><td>미확인 ✕</td></tr>
<tr><td>재고</td><td>EIA 주간 재고 23:30</td><td>미확인 (발표 전)</td></tr></table>"""
    cb = """<table><tr><th>중앙은행</th><th>정책금리</th><th>최근 결정</th><th>방향</th></tr>
<tr><td>연준</td><td>3.75~4.00%</td><td>9/16 +25bp, 12–0 (첫 인상 2023년 이후)</td><td class="t-orange">인상</td></tr>
<tr><td>ECB</td><td>예금 2.50%</td><td>9/10 +25bp, 만장일치, 10/29 추가 가능</td><td class="t-orange">인상</td></tr>
<tr><td>일본은행</td><td>1.25%</td><td>9/18 +25bp, 7–2 (1995년 이후 최고)</td><td class="t-orange">인상</td></tr>
<tr><td>한국은행</td><td>3.00%</td><td>8/27 +25bp (두 달 연속)</td><td class="t-orange">인상</td></tr></table>
<div class="small">일본은행 인상 사유는 자국 물가 상방 위험으로 보도되어 유가 때문이라는 근거는 없다(○). 유로존 8월 물가 3.3%, 에너지 물가 14.3%(○).</div>"""
    scen = """<table><tr><th>시나리오</th><th>조건</th><th>시장 경로</th><th>한국</th></tr>
<tr><td>{}</td><td>미국이 이란 제안 수용, 통항 회복 확인, EIA 재고 증가</td><td>유가 하락 지속 → PCE 둔화 시 금리 하락 → 성장주·장기채 복귀(통념)</td><td>항공·화학 비용 완화 후보(근거 약함)</td></tr>
<tr><td>{}</td><td>협상 교착, 수출 회복 지속</td><td>WTI 9/28~9/29 종가 범위(92.60~89.38달러)에서 등락, 장기금리는 물가 자료에 좌우</td><td>외국인 수급은 금리·반도체가 결정</td></tr>
<tr><td>{}</td><td>협상 결렬·공격 재개, 항로 차질</td><td>9/28처럼 장중 급등(WTI 96.54달러) 후 종가 반응은 작았음(+0.2%). 종가로도 이어지면 반대급부 실패</td><td>물가·금리 압력 재확대</td></tr></table>""".format(badge('완화', 'teal'), badge('기본', 'blue'), badge('악화', 'red'))
    return f"""<h1>Oil, War and Rates</h1><div class="sub">유가·중동 전쟁의 작동 경로와 각국 금리 반응. 협상 발언과 실제 이행을 구분한다.</div>
<h2>현재 작동 경로와 반대 방향의 조건</h2>
<div class="grid2"><div class="card bar-l"><div class="h">지금 작동하는 경로 (원인)</div><div class="v">전쟁·호르무즈 차질 → 공급·운임 → 유가 → 물가 → 각국 금리. 오늘은 앞 두 단계가 <b>완화 신호</b>(수출 회복, 유가 −3.5%)를 보이는데 마지막 단계(금리)는 그대로다.</div></div>
<div class="card bar-l"><div class="h">반대 방향이 되려면 (반대급부 이행)</div><div class="v">발언이 아니라 <b>통항 수치와 재고</b>가 바뀌어야 한다: 호르무즈 통항 재개 확인 + EIA 재고 증가 + 유가가 9/29 종가(89.38달러) 아래 유지. 전달 톱니(각국 긴축)는 시차로 계속 돈다.</div></div></div>
<h2>협상·제안과 실제 이행의 구분</h2>{tbl}
<h2>글로벌 전달: 4개 중앙은행이 모두 인상</h2>{cb}
<h2>시나리오</h2>{scen}"""


def p7():
    tree = """<div class="chain">
<div class="node blue"><div class="a">1 발언 반복</div><div class="b">Amodei·Altman·Musk(9/14), Gates(9/25~28) · <b>확인</b></div></div><div class="arw">→</div>
<div class="node blue"><div class="a">2 행동으로 이동</div><div class="b">GPT-6.1 Astra 출시 취소·훈련 중단(9/28, ○) · <b>확인</b></div></div><div class="arw">→</div>
<div class="node gray"><div class="a">3 주문 감소</div><div class="b">GPU·HBM 주문 하향 자료 없음 · <b>미확인</b></div></div><div class="arw">→</div>
<div class="node gray"><div class="a">4 capex·실적 하향 반복</div><div class="b">알파벳 capex 오히려 상향 · <b>미확인</b></div></div></div>"""
    four = """<table><tr><th>구분</th><th>사실</th><th>시장가격</th><th>실물</th></tr>
<tr><td>발언</td><td>9/14 Amodei 에세이 &quot;Pausing the AI Frontier&quot;, Altman·Musk 동조. 9/25~28 Gates &quot;10억 명 사망 가능&quot;</td><td>9/14 SOX 약 −6%, SK하이닉스 미국 −7%, KOSPI −3.3%. 같은 날 미 10년 5% 돌파(교란)</td><td>기업의 자본계획·훈련 예산 변경 신호 없음(○)</td></tr>
<tr><td>행동</td><td>9/28 OpenAI 에이전트 이탈 사고 뒤 최고 성능 모델 훈련·평가 중단, 출시 취소 (WSJ 인용 ○). 3개월 내 두 번째</td><td>미국장 ARM −8.7%, 인텔 −5.67%, SK하이닉스 ADR −5.3%. 사이버보안주 급등 보도</td><td>주문 변화 자료 없음</td></tr>
<tr><td>반응 둔화?</td><td>9/29 새 악재 없음</td><td>SOX +1.31% 반등 (표본 1일)</td><td>—</td></tr></table>"""
    korea = """<table><tr><th>영역</th><th>확인된 것</th><th>한국 연결</th><th>등급</th></tr>
<tr><td>HBM·메모리 (G8)</td><td>스팟 HBM이 계약가의 4~5배, 2027 가격 +50%↑ 전망. 마이크론 FQ4 예상 매출 약 510억~512억달러(+353%)</td><td>SK하이닉스·삼성전자. 8월 반도체 수출 466.5억달러(+209.0%)</td><td class="num">○ / ○*</td></tr>
<tr><td>전력 (G7)</td><td>GE Vernova 백로그·슬롯 116GW(7/22), 지멘스 69GW, 두산에너빌리티 누적 24기. 엔진·연료전지·원전·계통으로도 분산(○*)</td><td>주기기·변압기·전선(sectors.json power). 수주의 실적 전환에 시차</td><td class="num">○ / ○*</td></tr>
<tr><td>AI 자금 (G10)</td><td>알파벳 capex 1,950억~2,050억달러로 상향, 주가 −7.13%, 잉여현금흐름 −59억달러</td><td>capex 하향 시 G7·G8 동반. 직접 한국 반응 자료 ✕</td><td class="num">○</td></tr></table>"""
    return f"""<h1>AI and Semiconductors</h1><div class="sub">발언 · 행동 · 시장가격 · 실물 자료를 분리해서 본다. AI 발언을 곧바로 반도체 수요 감소로 연결하지 않는다.</div>
<h2>AI 뉴스 판단 트리와 현재 위치</h2>{tree}
<div class="okbox"><b>판정: 2단계까지 확인.</b> 특정 프로젝트 지연 가능성과 심리 조정 수준이며, 반도체 실물 전망 하향(3~4단계 반복 확인)의 근거는 아직 없다. 오히려 HBM 가격·수출·capex는 상향 쪽이다. 반증: 악재에도 주가가 버티고 수출·주문이 유지되면 영향 제한.</div>
<h2>발언·행동·가격·실물</h2>{four}
<h2>실물 쪽 확인 대상 (심리 쪽 반대급부에 맞서는 힘)</h2>{korea}
<div class="warnbox"><b>훈련 수요와 추론 수요, GPU·HBM·ASIC 영향은 다르다.</b> OpenAI의 중단이 어느 수요를 줄이는지 자료가 없다. 마이크론 예상 실적(+353%)은 회사 공시로 대조하지 못했고, 실적이 예상을 넘어도 가이던스가 약하면 주가가 내릴 수 있다는 경고가 요약들에 있다(○).</div>"""


def p8(root):
    ex, _ = _extra(root)
    hy, ccc, sf, y30 = ex.get('us_hy_oas'), ex.get('us_ccc_oas'), ex.get('sofr'), ex.get('us30y')
    def fv(it): return _fx(it)
    hyv, ccv, sfv = fv(hy), fv(ccc), fv(sf)
    gauge = '<div class="gauge"><div>1 안정</div><div class="on">2 경계 (현재)</div><div class="na">3 압박</div><div class="na">4 강제매도</div></div>'
    watch = """<table><tr><th>축</th><th>지표</th><th>오늘 값</th><th>상태</th></tr>
<tr><td rowspan="4"><b>주가</b><br><span class="small">판정 가능</span></td><td>S&amp;P 500 · 나스닥</td><td>−0.16% · −0.09% 하락</td><td>{}</td></tr>
<tr><td>SOX</td><td>+1.31% 상승 (9/28 −1.6%△)</td><td>{}</td></tr>
<tr><td>VIX</td><td>16.04 (전일 16.07)</td><td>{}</td></tr>
<tr><td>미 10년 · 30년</td><td>5.282% · 5.61% (20년 최고)</td><td>{}</td></tr>
<tr><td rowspan="3"><b>신용</b><br><span class="small">부분 판정</span></td><td>미국 하이일드 OAS · CCC 이하 OAS (FRED, 관측일 9/28)</td><td>HY @@hy0@@ (@@hy1@@) · CCC @@cc0@@ (@@cc1@@). 수준을 가를 임계값은 달님 미정</td><td>{}</td></tr>
<tr><td>한국 AA− 회사채 스프레드</td><td>0.679%p (전일 0.669, +1bp 확대)</td><td>{}</td></tr>
<tr><td>민간신용</td><td>Fitch 부도율 9월 6.3%, 환매 게이트 보도(○)</td><td>{}</td></tr>
<tr><td rowspan="2"><b>펀딩</b><br><span class="small">부분 판정</span></td><td>SOFR (FRED, 관측일 9/28) · 레포시장</td><td>SOFR @@sf0@@ (@@sf1@@). 레포시장은 미수집</td><td>{}</td></tr>
<tr><td>회사채 발행 취소·가산금리</td><td>자료 없음</td><td>{}</td></tr>
<tr><td rowspan="2"><b>시장 기능</b><br><span class="small">판정 불가</span></td><td>국채 입찰 수요 · MOVE</td><td>미수집</td><td>{}</td></tr>
<tr><td>마진콜·환매·강제청산</td><td>보도 확인 못 함</td><td>{}</td></tr></table>""".format(
        badge('경계', 'orange'), badge('반등 1일', 'blue'), badge('평온', 'teal'), badge('압박 후보', 'red'), badge('확대 방향', 'orange'), badge('안정', 'teal'), badge('후보 신호', 'orange'), badge('이상 신호 없음', 'teal'), badge('미확인', 'gray'), badge('미확인', 'gray'), badge('미확인', 'gray'))
    watch = watch.replace('@@hy0@@', hyv[0]).replace('@@hy1@@', hyv[1]).replace('@@cc0@@', ccv[0]).replace('@@cc1@@', ccv[1]).replace('@@sf0@@', sfv[0]).replace('@@sf1@@', sfv[1])
    chk = """<table><tr><th>4단계 후보 조건 (GPT 지침서 예시)</th><th>오늘 상태</th><th>판정</th></tr>
<tr><td>미 10년 5.30% 이상 안착</td><td>5.282% (9/29 종가). 0.018%p 아래, 안착 여부는 며칠 봐야 함</td><td>{}</td></tr>
<tr><td>나스닥 하루 −2%~−3% 또는 고점 대비 −15%</td><td>9/28 −0.9%, 9/29 −0.09%. 고점 대비 값 ✕</td><td>{}</td></tr>
<tr><td>HY·CCC OAS 추가 확대</td><td>1일 확대 방향(HY @@hy1@@ · CCC @@cc1@@). 추가 확대 여부는 며칠 봐야 함</td><td>{}</td></tr>
<tr><td>SOFR·레포시장 이상</td><td>SOFR @@sf0@@ 변화 없음(관측). 레포시장 미수집</td><td>{}</td></tr>
<tr><td>회사채·국채 발행 기능 저하</td><td>자료 없음</td><td>{}</td></tr>
<tr><td>마진콜·강제청산 확인</td><td>보도 확인 못 함</td><td>{}</td></tr></table>""".format(badge('근접·미충족', 'orange'), badge('미충족', 'teal'), badge('부분 충족', 'orange'), badge('미충족', 'teal'), badge('미확인', 'gray'), badge('미확인', 'gray'))
    chk = chk.replace('@@hy1@@', hyv[1]).replace('@@cc1@@', ccv[1]).replace('@@sf0@@', sfv[0])
    return f"""<h1>Credit and Forced Selling</h1><div class="sub">위험 3단계(압박)와 4단계(강제매도)를 구분한다. 숫자 하나로 단계를 바꾸지 않고 주가·신용·펀딩 세 축의 동시성과 지속성을 본다.</div>
<h2>위험단계 계기판</h2>{gauge}
<div class="redbox"><b>주가 축만 완전 판정, 신용·펀딩은 부분 판정.</b> HY·CCC 스프레드는 확대 방향이나 수준 기준이 없고, SOFR은 변화가 없지만 레포·발행 자료가 없다. “2단계 경계”는 <b>잠정</b>이다. 자료가 없는 레포시장·발행·MOVE를 안정으로 읽지 않는다. 30년물 20년 최고와 민간신용 6.3%는 후보 신호일 뿐 확인 지표가 없다.</div>
<h2>감시판</h2>{watch}
<h2>4단계 후보 점검</h2>{chk}
<div class="note">4단계 임계값(5.30%, −2%~−3%, −15%)은 GPT 지침서가 든 예시이며 유튜버 기준과 겹친다. 달님이 확정하기 전에는 참고 표시일 뿐 규칙이 아니다.</div>"""


def p9():
    map_tbl = """<table><tr><th>지배 흐름</th><th>반대급부 (작동 조건)</th><th>자금 이동 후보</th><th>근거</th><th>오늘</th></tr>
<tr><td>G1 고금리</td><td>PCE·성장 둔화로 금리 하락</td><td>현금·단기채·은행 → 장기채·성장주 (경기 악화형이면 방어주)</td><td>통념</td><td>{}</td></tr>
<tr><td>G2 고유가</td><td>협상·수출 회복으로 유가 하락</td><td>에너지·조선 → 항공·화학·소비</td><td>통념 (조선 −2.84% ○)</td><td>{}</td></tr>
<tr><td>AI 성장 (심리·가격)</td><td>G3 AI 우려</td><td>대형 반도체 → 사이버보안·KOSDAQ·개인</td><td>관측 (제목 ○)</td><td>{}</td></tr>
<tr><td>AI 성장 (실물)</td><td>capex 하향, HBM 가격 하락, 백로그 둔화</td><td>반도체·전력기기 → 현금·방어</td><td>통념</td><td>{}</td></tr>
<tr><td>AI 재반전</td><td>마이크론 가이던스 양호, capex 유지</td><td>사이버보안·KOSDAQ → 대형 반도체</td><td>통념</td><td>{}</td></tr>
<tr><td>G5 외국인 매도</td><td>현물·선물 동반 순매수, 원화 안정</td><td>개인·기관 → 외국인 복귀</td><td>통념</td><td>{}</td></tr>
<tr><td>G6 스트레스</td><td>VIX 급등, 신용 스프레드 확대</td><td>주식 → 현금·달러·국채·금</td><td>통념</td><td>{}</td></tr></table>""".format(
        badge('미작동', 'gray'), badge('초기 작동', 'teal'), badge('작동', 'blue'), badge('미작동', 'gray'), badge('미확인', 'gray'), badge('미작동', 'gray'), badge('미점등', 'gray'))
    kr = """<div class="grid2">
<div class="card bar-l"><div class="k">한국에 유리한 톱니</div><div class="v">• 반도체 수출 증가: 9/1~20 +259.4%, 비중 47.8%<br>• 유가 하락(WTI −3.5%): 수입물가·항공·화학 비용 부담 완화 후보<br>• KOSDAQ 상대 강세: 대형주 밖 수급 분산</div></div>
<div class="card bar-l"><div class="k">한국에 불리한 톱니</div><div class="v">• 미 장기금리 상승(30년 5.61%)과 외국인 순매도(약 −2.90조원)<br>• 지수의 반도체 편중(삼성전자+SK하이닉스 시총 52% 초과)<br>• 8월 생산 −1.3%·소매 −1.8%·설비투자 −9.5% 감소(일회성 요인 보도)</div></div></div>"""
    rules = """<table><tr><th>규칙 (달님 임계 확정 전 임시)</th><th>오늘 값</th><th>상태</th></tr>
<tr><td><b>유지</b> — 금리 상승에도 나스닥과 반도체 실적 전망이 유지</td><td>나스닥 −0.09%(9/29). 반도체 실적 전망은 마이크론 발표 전</td><td>{}</td></tr>
<tr><td><b>위험축소 후보</b> — 미 10년 임계(예시 5.30%) 이상 + 나스닥 급락 + HY OAS 확대가 같은 날 중첩</td><td>10년 5.282%(근접), 나스닥 −0.09%, HY OAS 확대 방향(+0.09%p, 관측일 9/28)</td><td>{}</td></tr>
<tr><td><b>재진입 후보</b> — 유가 5거래일 하락 + 미 10년 예시 5.10% 아래 + 외국인 3일 순매수 또는 반도체 악재 둔감화</td><td>유가 −5.6%(혼합 ○*) 충족, 10년 5.282% 미충족, 외국인 순매도 지속</td><td>{}</td></tr>
<tr><td><b>스트레스 점등</b> — VIX 상승 + 신용 스프레드 확대 동반</td><td>VIX 16.04 평온, 신용 스프레드는 확대 방향(HY·CCC, 관측일 9/28)이나 VIX 동반 상승 없음</td><td>{}</td></tr>
<tr><td><b>AI 재반전</b> — 마이크론 가이던스 양호 + 외국인 반도체 순매도 축소</td><td>실적 발표 전</td><td>{}</td></tr></table>""".format(
        badge('미확인', 'gray'), badge('미충족', 'teal'), badge('미충족', 'teal'), badge('미확인', 'gray'), badge('미확인', 'gray'))
    ban = """<div class="warnbox"><b>판단 금지 규칙.</b> CEO 발언 한 번, 협상 기사 한 건, 환율 하루 방향만으로 전면 매수·매도를 판단하지 않는다. 이 보고서는 신호 점등 여부까지만 표시하며 행동은 달님이 사전에 적은 규칙으로 정한다.</div>"""
    return f"""<h1>Korea and Action Rules</h1><div class="sub">한국 노출 경로, 반대급부가 작동할 때의 자금 이동, 사전에 정한 규칙의 충족 여부</div>
<h2>한국에 유리한 톱니와 불리한 톱니</h2>{kr}
<h2>반대급부와 자금 이동 지도</h2>{map_tbl}
<div class="note">관측은 KOSPI −2.70% 대 KOSDAQ +0.25%(9/28), −0.27% 대 +0.38%(9/29), 외국인·기관 매도와 개인 매수, AI 우려일의 사이클 대체 수혜(사이버보안) 보도다. “통념”은 저장소 data/axes.json의 Claude 초안이며 달님 판별 전이다.</div>
<h2>행동 규칙: 충족 0 · 미충족 2 · 미확인 3</h2>{rules}{ban}"""


def p10():
    src = [
        ('S1', '미국 마감·금리', 'AP (Toledo Blade 게재) 9/29', '○'),
        ('S2', '유가 결제가', 'Yahoo 게재 Reuters 9/29, Euronews·CNBC 9/28, Yahoo 9/25', '○'),
        ('S3', '연준 9/16 결정·윌리엄스', 'CNBC 9/16, US News 9/29', '○'),
        ('S4', '이란 협상·사우디 수출', 'Al Jazeera 9/29, CNBC 9/25', '○'),
        ('S5', 'ECB·BOJ·글로벌 채권', 'CNBC 9/10·9/18·9/3, CNN 9/14, CNBC 9/24', '○'),
        ('S6', 'AI 속도조절·OpenAI·Gates', 'CNN·CNBC 9/14, Bloomberg(WSJ 인용) 9/28, Axios 9/25', '○'),
        ('S7', '전력·HBM·마이크론', 'GE Vernova 2Q, POWER, 트렌드포스, 서울경제, Investing.com (일부 ○*)', '○ / ○*'),
        ('S8', 'AI 자금', 'CNBC 7/28, Yahoo 7/23', '○'),
        ('S9', '한국 마감·수급·업종', '아시아경제·뉴스핌 9/29, 서울신문·머니투데이 9/28·9/29', '○'),
        ('S10', '한국 수출·한은·산업활동', '헤럴드·폴리뉴스, 서울신문·뉴스핌 8/27, 이투데이·아시아경제 9/30', '○'),
        ('S11', 'KOSPI 고점·외국인 누적', '한국경제 6/19, 다음 6/3·9/1', '○'),
        ('S12', 'PCE 예상', 'AOL (WSJ 설문 인용)', '○'),
        ('S13', '저장소 수집값', 'facts/macro.json, macro_history.json, macro_extra.json (FRED·ECOS 공식, 코드 수집)', 'A/D 또는 A/F 수준'),
    ]
    def acc(d):
        if d.startswith('A/D'):
            return 'A/D'
        return 'B/S 일부 C/S' if '*' in d else 'B/S'
    st = ''.join(f'<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td class="num">{acc(d)}</td></tr>' for a, b, c, d in src)
    return f"""<h1>Sources and Limits</h1><div class="sub">출처 번호, 자료 기준시각, 미확인 항목, 신뢰도 범례, 다음 보고서 비교 기준, 정정 이력</div>
<div class="redbox"><b>제한판 — 가장 큰 한계: 기사 원문·공식 통계 원문을 열지 못했다(S).</b> 코드 수집값(FRED·ECOS, S13)만 A/D이다. 이 환경에서는 Reuters, AP, 연준, FRED, 정부 사이트 본문 접속이 막혀 있다. 아래 출처는 모두 검색 결과의 링크와 요약이며 원문 대조는 달님이 링크를 열어 하는 단계다. 링크 전체 목록은 Docs 보고서와 docs/reports/2026-09-30.md에 있다.</div>
<div class="grid2"><div><h2>출처와 등급</h2><table><tr><th>번호</th><th>주제</th><th>출처</th><th class="num">권위/접근</th></tr>{st}</table></div>
<div><h2>신뢰도 범례</h2>
<table><tr><th>표시</th><th>뜻</th></tr>
<tr><td>◎ (지침서 A·B)</td><td>서로 다른 출처 2곳 이상 일치 또는 공식 원자료 확인</td></tr>
<tr><td>○</td><td>검색 요약 1곳에서만 확인. 원문 미열람</td></tr>
<tr><td>○*</td><td>이해관계가 있거나 2차 가공된 출처 (블로그, 분석 사이트, SPAC 공시)</td></tr>
<tr><td>△</td><td>출처끼리 충돌. 결론에서 제외</td></tr>
<tr><td>A/B/C · D/R/S/F/U</td><td>권위(A 공식·B 통신사·C 2차) / 접근(D 직접 확인·R 재게시·S 검색요약·F 제공파일·U 실패). S만 있는 숫자는 핵심 결론의 단독 근거가 아니다</td></tr>
<tr><td>✕ · 미확인</td><td>확인 못 함. 안정으로 읽지 않음</td></tr>
<tr><td>가설 (지침서 C)</td><td>인과 추론. 반증 조건과 다음 검증자료를 함께 표시</td></tr></table>
<h2>미확인 항목</h2><ul class="small">
<li>원/달러: ECOS 매매기준율 9/29 1,360.0과 시장 종가(검색 1,357.60·GPT 1,356.7)는 정의·시각이 다름. 같은 정의의 5일 값 미대조</li>
<li>미 2년 9/29 종가, 신규 4지표(30년·HY·CCC·SOFR)의 기간 시계열, 레포시장, MOVE</li>
<li>외국인 현물·선물 분리, 투자자별·업종별 원자료(KRX)</li>
<li>전략비축유 4,000만 배럴 제안, 마이크론 예상 실적의 회사 공시 대조</li>
<li>한은 10월 금통위 날짜, 9월 소비자물가 발표일, KOSPI 6/19 최고 종가의 KRX 대조</li></ul>
<h2>다음 보고서 비교 기준</h2><p class="small">analysis/issue_ledger.json의 G1~G10 상태를 이어받고 오늘 값을 “이전”으로 쓴다. 전일 종가·장중가·선물가를 한 표에 섞지 않는다.</p>
<h2>정정 이력</h2><ul class="small">
<li>v0 초안의 “유가 하락 미확인”(링크 주소 오독)을 정정: 결제가 하락 확인(◎)</li>
<li>미 10년 후장 호가 5.255%(GPT)를 종가 5.282%로 정정</li>
<li>한국 산업활동을 “내수 둔화 강화”에서 “일회성 요인 가능성”으로 정정</li>
<li>G3를 지배 흐름이 아니라 AI 성장에 대한 반대급부로 재분류</li></ul></div></div>"""


# ---------------------------------------------------------------- 4·5·7·9쪽 하단 보강 (근거 없는 칸은 '미확인'으로 둔다)
def _chain(nodes):
    parts = []
    for i, (a, b, col) in enumerate(nodes):
        parts.append(f'<div class="node {col}"><div class="a">{a}</div><div class="b">{b}</div></div>')
        if i < len(nodes) - 1:
            parts.append('<div class="arw">→</div>')
    return '<div class="chain">' + ''.join(parts) + '</div>'


def _x4():
    steps = [
        ('글로벌 사건', '이란 협상 교착 · 연준 9/16 인상 · OpenAI 훈련 중단', '보도 확인(B/S)', ('확인', 'blue'), '유가·금리·달러: WTI −3.5%, 미 10년 +4bp, DXY 직전값 101.372(저장소)', ('부분 확인', 'orange'), '유가는 내렸는데 금리는 올라 방향 불일치'),
        ('유가·금리·달러', 'WTI −3.5% · 10년 +4bp · 30년 +7bp(9/28 FRED)', '수치 확인(D·S 혼합)', ('부분 확인', 'orange'), '미국 업종: SOX +1.31%, 나스닥 −0.09%', ('부분 확인', 'orange'), '업종별 반응 자료는 SOX·나스닥 지수뿐'),
        ('미국 업종', 'SOX 반등, 사이버보안주 급등 보도, 알파벳 −7.13%', '지수 확인 · 업종 S', ('부분 확인', 'orange'), '원/달러·외국인: 외국인 약 −2.90조원, 원/달러 정의 차이', ('가설', 'orange'), '미국 반등과 한국 매도가 엇갈림. 원인 미확정'),
        ('원/달러·외국인 수급', 'ECOS 매매기준율 1,360.0(9/29) · 외국인 현물 약 −2.90조원(S)', '환율 D · 수급 S', ('부분 확인', 'orange'), '한국 업종: 반도체 87% 매도(단일 요약)', ('부분 확인', 'orange'), '선물·투자자별 원자료(KRX) 미수집'),
        ('한국 업종', '반도체 매도, 조선 −2.84%(S), 방어 섹터 자료 없음', '반도체 S · 방어 미확인', ('부분 확인', 'orange'), '실물지표: 반도체 수출 +259.4%(9/1~20)', ('미확인', 'gray'), '주가·수급과 실물이 다른 방향. 10/1 확정치 전'),
        ('확인할 실물지표', '10/1 9월 수출 · 마이크론 FQ4 · 21:30 PCE · EIA 재고', '발표 전', ('미확인', 'gray'), '-', ('미확인', 'gray'), '발표되면 이 칸을 채운다'),
    ]
    tr = ''.join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{badge(*d)}<br><span class='small'>{c}</span></td><td>{esc(e)}</td><td>{badge(*f)}</td><td>{g}</td></tr>" for a, b, c, d, e, f, g in steps)
    ch = _chain([('글로벌 사건', '협상·긴축·AI', 'blue'), ('유가·금리·달러', '방향 불일치', 'orange'), ('미국 업종', 'SOX·보안주', 'orange'), ('원/달러·외국인', '수급 −2.90조', 'red'), ('한국 업종', '반도체 매도', 'red'), ('실물지표', '발표 전', 'gray')])
    return f"""<h2>톱니 6단계 연결 상태 <span class="small">(각 연결 = 앞 단계에서 다음 단계로 이어졌는지)</span></h2>{ch}
<div class="tight"><table><tr><th>단계</th><th>오늘 관측</th><th>관측 상태</th><th>다음 단계로 연결</th><th>연결 상태</th><th>비고</th></tr>{tr}</table></div>
<div class="note">연결 상태는 확인 · 부분 확인 · 가설 · 미확인 네 가지만 쓴다. 같은 방향의 숫자가 양쪽에서 확인될 때만 “확인”이며, 오늘은 어느 연결도 “확인”이 아니다.</div>"""


def _x5(root):
    L = _ledger(root)
    today = dt.date(2026, 9, 30).isoformat()
    cats = {'신규 점화': [], '유지': [], '강화': [], '약화': [], '소멸 후보': [], '재점화': [], '판정 보류': []}
    for it in L['issues']:
        d = it['direction']
        if it['stage'] == 0 or d.startswith('양방향') or '반대급부 작동' in d:
            cats['판정 보류'].append(f"{it['id']} ({d})")
        elif it['first_seen'] == today:
            cats['신규 점화'].append(f"{it['id']} (최초 근거일 {today[5:]})")
        elif '약화' in d:
            cats['약화'].append(f"{it['id']} ({d})")
        elif d.startswith('유지'):
            cats['유지'].append(f"{it['id']}")
    rows = ''
    for k, v in cats.items():
        ref = ', '.join(v) if v else '해당 없음(장부 필드 기준)'
        rows += f"<tr><td style='white-space:nowrap'><b>{k}</b></td><td style='white-space:nowrap'>기준일 장부로 비교 불가</td><td>{esc(ref)}</td></tr>"
    return f"""<h2 style="margin-top:2mm">전일 대비 이슈 변화</h2>
<div class="tight"><table><tr><th>구분</th><th>전일 대비 판정</th><th>오늘 장부의 방향 필드 (참고, 전일 대비 아님)</th></tr>{rows}</table></div>
<div class="warnbox"><b>오늘이 장부의 첫 기록일이다.</b> 전일 장부가 없어 어느 구분도 “변화”로 판정하지 않는다. 오른쪽 열은 오늘 장부의 방향 필드를 옮긴 것이다. 소멸 후보는 세 조건이 함께 확인돼야 하며 오늘은 없다.</div>"""


def _x7():
    ch = _chain([('AI 투자 확대', '알파벳 capex 상향', 'blue'), ('데이터센터 전력 수요', '수요 전망', 'gray'), ('전력망 접속 지연', '자료 없음', 'gray'), ('가스발전·터빈·변압기·냉각', '백로그 116GW', 'orange'), ('원자력', '장기 대안', 'gray'), ('한국 전력기기·반도체', '주가·실적 미확인', 'gray')])
    rows = [
        ('AI 투자 확대', '알파벳 2026 capex 1,950억~2,050억달러로 상향(회사 계획)', '알파벳 주가 −7.13%(잉여현금흐름 −59억달러)', '계획 상향은 있으나 실제 집행 미확인', ('부분 확인', 'orange')),
        ('데이터센터 전력 수요', 'AI 기업의 전력 부족 발언 반복(장부 G7)', '미확인', '수요 전망 수치 원문 미열람', ('가설', 'orange')),
        ('전력망 접속 지연', '발언·보도 미확인', '미확인', '접속 대기·허가 지연 자료 없음', ('미확인', 'gray')),
        ('가스발전·가스터빈·변압기·냉각', '수요가 가스터빈으로 흐른다는 발언은 있음(장부 G7)', '터빈·전력기기 종목 주가 자료 없음', 'GE Vernova 백로그·슬롯 116GW(7/22), 지멘스 69GW, 두산에너빌리티 누적 24기 (회사·보도, S). 엔진·연료전지·계통은 ○*', ('부분 확인', 'orange')),
        ('원자력 장기 대안', '시간이 걸린다는 논지', '미확인', '인허가·착공 자료 없음', ('미확인', 'gray')),
        ('한국 전력기기·반도체', '두산에너빌리티 등 언급(S)', '한국 업종 주가·수급 자료 없음', '수주의 실적 전환에는 시차. 8월 반도체 수출 466.5억달러(+209.0%)는 별도 경로', ('가설', 'orange')),
    ]
    tr = ''.join(f"<tr><td><b>{a}</b></td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td><td>{badge(*e)}</td></tr>" for a, b, c, d, e in rows)
    return f"""<h2>AI 전력 부족 톱니바퀴: 수요가 가스터빈으로 흐르는가</h2>{ch}
<div class="tight"><table><tr><th>단계</th><th>발언</th><th>시장가격</th><th>수주·설비투자 증거</th><th>상태</th></tr>{tr}</table></div>
<div class="note">발언, 시장가격, 수주·설비투자 증거를 칸으로 나눴다. 발언만 있는 단계는 “가설”, 자료가 없으면 “미확인”이다. 섹터 정의(sectors.json)는 건드리지 않고 흐름만 본다.</div>"""


def _x9(root):
    ex, _ = _extra(root)
    hy = ex.get('us_hy_oas', {})
    ch = _chain([('글로벌 위험', 'VIX 평온 · HY 확대', 'orange'), ('달러·원화', 'DXY · 원/달러', 'gray'), ('외국인 현물·선물', '−2.90조 · 선물 ✕', 'red'), ('KOSPI·KOSDAQ', '−0.27% · +0.38%', 'blue'), ('반도체·방어·에너지', '방어·에너지 ✕', 'gray'), ('다음 확인자료', 'KRX 원자료', 'gray')])
    rows = [
        ('글로벌 위험 변화', f"VIX 16.04(평온), HY OAS {hy.get('value', '—')}%p({hy.get('change', 0):+.2f}, 관측일 {hy.get('as_of', '—')}), 미 10년 5.282%", ('부분 확인', 'orange'), '수준 기준 없음'),
        ('달러·원화', 'DXY 직전 수집값 101.372, ECOS 매매기준율 1,360.0(9/29). 시장 종가 1,357.60·1,356.7과 정의가 달라 합치지 않음', ('부분 확인', 'orange'), '같은 정의 5일 값'),
        ('외국인 현물·선물', '현물 약 −2.90조원(보도 요약 S). 선물·투자자별 원자료 없음', ('가설', 'orange'), 'KRX 수급'),
        ('KOSPI·KOSDAQ', 'KOSPI 6,870.81(−0.27%), KOSDAQ 849.80(+0.38%)', ('확인', 'blue'), '복수 확인'),
        ('반도체·방어주·에너지', '반도체 87% 매도(단일 요약 S), 조선 −2.84%(S). 방어 섹터·에너지 업종 자료 없음', ('미확인', 'gray'), '업종 지수'),
    ]
    tr = ''.join(f"<tr><td style='white-space:nowrap'><b>{a}</b></td><td>{esc(b)}</td><td>{badge(*c)}</td><td>{esc(d)}</td></tr>" for a, b, c, d in rows)
    return f"""<h2>한국 자금 이동 지도: 글로벌 위험이 어디로 옮겨가는가</h2>{ch}
<div class="tight"><table><tr><th>단계</th><th>오늘 관측</th><th>상태</th><th>다음 확인자료</th></tr>{tr}</table></div>
<div class="redbox"><b>KRX 원자료가 없어 자금 이동을 사실로 단정하지 않는다.</b> 방어주·에너지로 이동했는지는 확인할 자료가 없고, 위 지도는 확인 순서표이지 결론이 아니다. 다음 확인: 10/1 수출 · 마이크론 · 21:30 PCE.</div>"""


def build(root):
    pages = [
        ('Executive Dashboard', p1()), ('Change Board', p2(root)), ('Actual Data Charts', p3(root)),
        ('World-to-Korea Transmission', p4() + _x4()), ('Issue Ledger', p5(root) + _x5(root)), ('Oil, War and Rates', p6()),
        ('AI and Semiconductors', p7() + _x7()), ('Credit and Forced Selling', p8(root)), ('Korea and Action Rules', '<div class="tight">' + p9() + _x9(root) + '</div>'),
        ('Sources and Limits', p10()),
    ]
    out = []
    for i, (name, body) in enumerate(pages, 1):
        out.append(page(i, TOTAL, TITLE, DATE_TXT, VER, body, FOOT))
    return out
