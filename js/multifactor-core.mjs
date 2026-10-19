// v 20261019-1  multifactor-core.mjs — multifactor.html 의 순수 계산(그룹 나누기·성향 설문·정렬·서식). 브라우저와 Node 시험에서 같이 쓴다.
// 점수·순위 자체는 서버(scripts/multifactor_kr.py)가 계산해 analysis/multifactor_kr.json 에 넣는다. 여기서는 다시 계산하지 않는다.

export const STYLE_KEYS = ["base", "value_growth", "trend_growth", "contrarian"];
export const FACTOR_KEYS = ["mom_price", "mom_vol", "per", "pbr", "rev", "op", "ni", "roe"];
const FACTOR_NAMES = { mom_price: "모멘텀 주가", mom_vol: "모멘텀 거래량", per: "PER", pbr: "PBR", rev: "매출증가", op: "영업이익증가", ni: "순이익증가", roe: "ROE" };

// 스타일 설명(우리 표현). 지표 구성은 JSON 의 styles 에서 읽고, 여기서는 읽기용 문구만 둔다.
export const STYLE_TEXT = {
  base: { name: "기본", short: "8개 지표 전체", fits: "시장 전체에서 균형 잡힌 종목을 보고 싶을 때", caution: "특정 성향에 맞춘 점수가 아니라 모든 지표를 같은 비중으로 평균한 값입니다." },
  value_growth: { name: "가치 성장", short: "밸류 + 퀄리티", fits: "싸면서 실적도 좋은 기업을 오래 가져가려는 성향", caution: "가치 회복에 시간이 걸리고 단기 테마 상승에는 늦게 반응할 수 있습니다." },
  trend_growth: { name: "추세 성장", short: "모멘텀 + 퀄리티", fits: "상승 흐름을 타되 실적이 받쳐주는 기업을 보려는 성향", caution: "시장 전체가 꺾이거나 추세가 바뀌면 손실이 커질 수 있습니다." },
  contrarian: { name: "역발상", short: "밸류 + 모멘텀", fits: "소외돼 싸졌다가 반등을 시작하는 종목을 찾는 성향", caution: "반등이 아니라 계속 하락하는 '떨어지는 칼날'일 수 있어 원인 확인이 필요합니다." },
};

// ---- 점수 그룹 나누기: 점수순(상위 먼저)으로 정렬된 목록을 N개 그룹으로. 남는 종목은 앞 그룹이 하나씩 더 가진다(예: 10종목 3그룹 → 4,3,3).
export function sortedByStyle(items, style) {
  return [...items].sort((a, b) => a.scores[style].rank - b.scores[style].rank || b.marcap - a.marcap);
}

export function groupItems(items, style, ngroup) {
  const n = Math.max(1, Math.min(Math.floor(ngroup), items.length || 1));
  const arr = sortedByStyle(items, style);
  const base = Math.floor(arr.length / n), extra = arr.length % n;
  const groups = [];
  let pos = 0;
  for (let g = 0; g < n; g++) {
    const size = base + (g < extra ? 1 : 0);
    const part = arr.slice(pos, pos + size);
    pos += size;
    const avg = part.length ? part.reduce((s, it) => s + it.scores[style].score, 0) / part.length : null;
    groups.push({ group: g + 1, items: part, avgScore: avg === null ? null : Math.round(avg * 10) / 10 });
  }
  return groups;
}

// ---- 성향 설문 (문항은 같은 주제를 우리 표현으로 새로 썼다. A=추세 성장 · B=가치 성장 · C=역발상)
export const OPTION_STYLE = { A: "trend_growth", B: "value_growth", C: "contrarian" };

export const SURVEY = [
  { q: "투자금을 얼마나 오래 굴릴 생각인가요?", o: { A: "몇 달 안에 결과를 보는 단기", B: "2년 이상 길게 가져가는 장기", C: "반년에서 2년 사이의 중기" } },
  { q: "시장이 크게 흔들릴 때 보통 어떻게 하나요?", o: { A: "추세가 꺾이면 빨리 정리한다", B: "기업 가치를 믿고 버틴다", C: "급락한 우량주를 추가로 살 기회로 본다" } },
  { q: "끌리는 투자 방식은 무엇인가요?", o: { A: "강하게 오르는 종목에 올라탄다", B: "저평가된 종목을 오래 보유한다", C: "부진하다가 막 반등하기 시작한 종목에 투자한다" } },
  { q: "종목을 볼 때 가장 먼저 확인하는 것은?", o: { A: "최근 주가와 거래량의 흐름", B: "PER·PBR처럼 가격 대비 가치", C: "실적 악화가 멈추고 좋아지는 신호" } },
  { q: "보유 종목이 오랫동안 제자리일 때 마음은?", o: { A: "더 잘 움직이는 종목으로 갈아탈까 고민한다", B: "기업 가치를 믿고 기다린다", C: "반등 신호가 오는지 지켜보며 준비한다" } },
  { q: "위험에 대한 생각에 가장 가까운 것은?", o: { A: "수익이 크다면 변동성은 감수한다", B: "싸게 사서 안전마진을 확보하는 게 최우선이다", C: "많이 떨어진 종목은 추가 하락 여지가 작다고 본다" } },
  { q: "기업 뉴스에서 가장 눈여겨보는 것은?", o: { A: "주가 관련 소식과 시장의 관심도", B: "재무 상태와 사업의 안정성", C: "실적 개선이나 신기술 같은 반전 신호" } },
  { q: "한 섹터를 고른다면 어디가 끌리나요?", o: { A: "AI·반도체처럼 빠르게 크는 혁신 섹터", B: "필수소비재·유틸리티처럼 경기에 덜 민감한 섹터", C: "한동안 침체됐다가 정책·기술 변화로 다시 주목받는 전통 산업" } },
  { q: "새 종목은 주로 어떻게 찾나요?", o: { A: "차트에서 거래량이 급증하거나 신고가를 낸 종목", B: "저PER·저PBR 종목 목록", C: "하락 뒤 실적이 좋아지고 있는 기업" } },
  { q: "전문가 의견 중 가장 믿음이 가는 것은?", o: { A: "요즘 가장 뜨겁게 오르는 종목을 짚어주는 의견", B: "저평가된 우량주를 찾아주는 의견", C: "바닥을 다지고 다시 오르기 시작하는 종목을 짚어주는 의견" } },
];

// answers: { 0:'A', 1:'C', ... } (문항 인덱스 → 선택). 전부 답해야 판정한다.
export function surveyResult(answers) {
  const counts = { A: 0, B: 0, C: 0 };
  let answered = 0;
  for (let i = 0; i < SURVEY.length; i++) {
    const a = answers && answers[i];
    if (a === "A" || a === "B" || a === "C") { counts[a]++; answered++; }
  }
  if (answered < SURVEY.length) return { complete: false, answered, missing: SURVEY.length - answered, counts };
  const max = Math.max(counts.A, counts.B, counts.C);
  const winners = ["A", "B", "C"].filter((k) => counts[k] === max);
  return { complete: true, answered, counts, tie: winners.length > 1, styles: winners.map((k) => OPTION_STYLE[k]) };
}

// ---- 표시용 서식
export function fmtNum(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  const d = a >= 1000 ? 0 : a >= 100 ? 0 : digits;
  return v.toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });
}
export function fmtFactor(key, v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (key === "per" || key === "pbr") return fmtNum(v, key === "pbr" ? 2 : 1) + "배";
  return fmtNum(v, 1) + "%";
}
export function fmtMarcap(won) {
  if (!Number.isFinite(won)) return "—";
  const jo = won / 1e12;
  return jo >= 1 ? jo.toFixed(jo >= 10 ? 0 : 1) + "조" : Math.round(won / 1e8).toLocaleString("ko-KR") + "억";
}

// 순위(%) → 칸 색 진하기(0.05~0.60). 1등에 가까울수록(작을수록) 진하다.
export function heatAlpha(rankPct) {
  const r = Math.min(100, Math.max(0, rankPct));
  return Math.round((0.6 * (100 - r) / 100 + 0.05) * 100) / 100;
}

// ---- 검색: 종목명 부분 일치(대소문자 무시) 또는 코드 앞부분 일치
export function searchItems(items, q) {
  const s = String(q || "").trim().toLowerCase();
  if (!s) return [];
  return items.filter((it) => it.name.toLowerCase().includes(s) || it.code.startsWith(s));
}

// ---- 정렬: key 가 'rank' 면 스타일 순위, 지표 키면 그 지표의 순위(%) 오름차순(좋은 것 먼저)
export function sortItems(items, style, key, dir = 1) {
  const val = (it) => (key === "rank" ? it.scores[style].rank : key === "name" ? it.name : it.ranks[key]);
  return [...items].sort((a, b) => {
    const x = val(a), y = val(b);
    const c = typeof x === "string" ? x.localeCompare(y, "ko") : x - y;
    return (c || a.scores[style].rank - b.scores[style].rank) * dir;
  });
}

export function flagText(flag) {
  if (String(flag).startsWith("filled:")) {
    const k = String(flag).slice(7);
    return "값이 없어 대상 종목의 중앙값으로 대체함(" + (FACTOR_NAMES[k] || k) + ")";
  }
  return ({
    per_unavailable: "PER이 없거나 0 이하(적자 가능) — 0 이하면 PER 순위는 최하위, 값이 없으면 중앙값으로 처리",
    pbr_unavailable: "PBR이 없거나 0 이하(자본잠식 가능) — 0 이하면 PBR 순위는 최하위, 값이 없으면 중앙값으로 처리",
    per_loss: "적자(EPS 0 이하)라 PER이 없음 — PER 순위는 최하위로 처리",
    pbr_loss: "자본잠식(BPS 0 이하)이라 PBR이 없음 — PBR 순위는 최하위로 처리",
    short_history: "상장 기간이 짧아 일부 기간(3개월·연간)이 빠진 평균",
    base_nonpositive: "전분기 값이 0 이하여서 증가율을 절댓값 기준으로 계산함(기저 효과 주의)",
    annual_missing: "연간 재무를 읽지 못함",
    quarter_missing: "분기 재무가 부족함",
  })[flag] || flag;
}
