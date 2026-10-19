// multifactor-core 단위 시험 — 실행: node --test tests/mf/multifactor-core.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  STYLE_KEYS, FACTOR_KEYS, SURVEY, OPTION_STYLE, groupItems, surveyResult, fmtNum, fmtFactor, fmtMarcap,
  heatAlpha, searchItems, sortItems, sortedByStyle, flagText,
} from "../../js/multifactor-core.mjs";

function mk(n) {
  return Array.from({ length: n }, (_, i) => ({
    code: String(100000 + i * 10), name: "종목" + (i + 1), marcap: 1e13 - i * 1e9,
    ranks: Object.fromEntries(FACTOR_KEYS.map((k, j) => [k, ((i * (j + 3)) % n) + 1])),
    scores: Object.fromEntries(STYLE_KEYS.map((s) => [s, { score: 10 + i, rank: i + 1, pct: 0 }])),
  }));
}

test("groupItems: 10종목 3그룹은 4,3,3 (남는 종목은 앞 그룹)", () => {
  const g = groupItems(mk(10), "base", 3);
  assert.deepEqual(g.map((x) => x.items.length), [4, 3, 3]);
  assert.equal(g[0].items[0].name, "종목1");           // 1그룹이 최상위
  assert.equal(g[2].items.at(-1).name, "종목10");
});

test("groupItems: 100종목 10그룹은 각 10개, 평균 점수 계산", () => {
  const g = groupItems(mk(100), "base", 10);
  assert.ok(g.every((x) => x.items.length === 10));
  assert.equal(g[0].avgScore, 14.5);                   // 점수 10..19 의 평균
});

test("groupItems: 그룹 수가 종목 수보다 크면 종목 수로 제한, 빈 입력 안전", () => {
  assert.equal(groupItems(mk(3), "base", 10).length, 3);
  assert.equal(groupItems([], "base", 3).length, 1);
});

test("groupItems: 스타일이 바뀌면 그 스타일의 순위로 나눈다", () => {
  const items = mk(6);
  items[0].scores.contrarian.rank = 6; items[5].scores.contrarian.rank = 1;
  const g = groupItems(items, "contrarian", 2);
  assert.equal(g[0].items[0].name, "종목6");
  assert.equal(sortedByStyle(items, "contrarian").at(-1).name, "종목1");
});

test("surveyResult: 미응답이면 판정하지 않고 남은 문항 수를 알려준다", () => {
  const r = surveyResult({ 0: "A", 1: "B" });
  assert.equal(r.complete, false); assert.equal(r.missing, 8);
});

test("surveyResult: 다수 선택이 스타일이 된다(A→추세, B→가치, C→역발상)", () => {
  const all = (x, y) => Object.fromEntries(SURVEY.map((_, i) => [i, i < 6 ? x : y]));
  assert.deepEqual(surveyResult(all("A", "B")).styles, ["trend_growth"]);
  assert.deepEqual(surveyResult(all("B", "C")).styles, ["value_growth"]);
  assert.deepEqual(surveyResult(all("C", "A")).styles, ["contrarian"]);
});

test("surveyResult: 동률이면 tie 와 두 스타일을 돌려준다", () => {
  const ans = Object.fromEntries(SURVEY.map((_, i) => [i, i < 5 ? "A" : "B"]));
  const r = surveyResult(ans);
  assert.equal(r.tie, true); assert.deepEqual(r.styles.sort(), ["trend_growth", "value_growth"]);
});

test("surveyResult: 잘못된 값은 응답으로 세지 않는다", () => {
  const r = surveyResult(Object.fromEntries(SURVEY.map((_, i) => [i, "Z"])));
  assert.equal(r.complete, false); assert.equal(r.answered, 0);
});

test("SURVEY: 10문항, 문항마다 A/B/C 보기가 있다", () => {
  assert.equal(SURVEY.length, 10);
  for (const s of SURVEY) assert.deepEqual(Object.keys(s.o), ["A", "B", "C"]);
  assert.deepEqual(Object.values(OPTION_STYLE).sort(), ["contrarian", "trend_growth", "value_growth"]);
});

test("서식: 결측은 대시, 단위와 자릿수", () => {
  assert.equal(fmtNum(null), "—"); assert.equal(fmtNum(NaN), "—");
  assert.equal(fmtFactor("per", 12.34), "12.3배"); assert.equal(fmtFactor("pbr", 1.234), "1.23배");
  assert.equal(fmtFactor("roe", 8.33), "8.3%"); assert.equal(fmtFactor("op", null), "—");
  assert.equal(fmtFactor("op", 1234.5), "1,235%");
  assert.equal(fmtMarcap(1.2628e15), "1263조"); assert.equal(fmtMarcap(5e10), "500억"); assert.equal(fmtMarcap(undefined), "—");
});

test("heatAlpha: 1등에 가까울수록 진하고 범위를 벗어나도 안전", () => {
  assert.ok(heatAlpha(5) > heatAlpha(95));
  assert.equal(heatAlpha(-10), heatAlpha(0)); assert.equal(heatAlpha(500), heatAlpha(100));
});

test("searchItems: 이름 부분 일치 또는 코드 앞부분, 빈 입력은 빈 결과", () => {
  const items = mk(30);
  assert.equal(searchItems(items, "종목3").length, 2);     // 종목3, 종목30
  assert.ok(searchItems(items, "종목3").every((x) => x.name.includes("종목3")));
  assert.equal(searchItems(items, "100000").length, 1);
  assert.deepEqual(searchItems(items, "  "), []);
});

test("sortItems: 지표 순위 오름차순, 내림차순 방향, 동순위는 스타일 순위", () => {
  const items = mk(8);
  const asc = sortItems(items, "base", "per", 1).map((x) => x.ranks.per);
  assert.deepEqual(asc, [...asc].sort((a, b) => a - b));
  const desc = sortItems(items, "base", "rank", -1);
  assert.equal(desc[0].name, "종목8");
  assert.equal(sortItems(items, "base", "name", 1)[0].name, "종목1");
});

test("flagText: 알려진 플래그는 설명, 모르는 플래그는 그대로", () => {
  assert.match(flagText("per_unavailable"), /적자/);
  assert.equal(flagText("zzz"), "zzz");
});

test("flagText: 중앙값 대체와 짧은 상장 기간 플래그", () => {
  assert.match(flagText("filled:roe"), /중앙값.*ROE/);
  assert.match(flagText("filled:mom_vol"), /거래량/);
  assert.match(flagText("short_history"), /상장 기간/);
});

test("평균 순위(2.5 같은 소수 순위)도 정렬·그룹 나누기가 동작한다", () => {
  const items = mk(4);
  items[1].scores.base.rank = 1.5; items[2].scores.base.rank = 1.5; items[0].scores.base.rank = 1; items[3].scores.base.rank = 4;
  // 동순위(1.5)는 시가총액이 큰 종목이 먼저, 그 뒤 4위
  assert.deepEqual(sortedByStyle(items, "base").map((x) => x.name), ["종목1", "종목2", "종목3", "종목4"]);
  assert.equal(groupItems(items, "base", 2)[0].items.length, 2);
});
