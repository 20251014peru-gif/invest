# -*- coding: utf-8 -*-
"""multifactor_kr 단위 시험 — 네트워크 없이 가짜 데이터로 검증한다.
실행: python -m unittest discover -s tests/mf -p "test_*.py" -v
책(2장)의 예시값을 재현한다: 순위 8개 [40,50,60,50,60,50,20,10] 의 평균 = 42.5,
가치 성장 예시(PER 22, PBR 44, ROE 24, 매출 9, 영업이익 12, 순이익 30) 의 평균 = 23.5(책 표에는 반올림 24).
책 패키지(MultiFactor 0.3.3)와의 실제 데이터 비교 결과는 docs/multifactor-kr.md 에 있다.
"""
import os, sys, json, tempfile, unittest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import multifactor_kr as mf


def _r(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _w(p, t):
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)


def price_df(n=260, start=100.0, step=0.5, vol=100000):
    idx = pd.date_range(end="2026-10-16", periods=n, freq="B")
    return pd.DataFrame({"Close": [start + step * i for i in range(n)], "Volume": [vol] * n}, index=idx)


def annual_df(per=10.0, pbr=1.0, eps=None, bps=None):
    idx = pd.to_datetime(["2023-12-01", "2024-12-01", "2025-12-01"])
    df = pd.DataFrame({"PER(배)": [8.0, 9.0, per], "PBR(배)": [0.8, 0.9, pbr], "영업이익": [1.0, 2.0, 3.0]}, index=idx)
    if eps is not None: df["EPS(원)"] = [100.0, 100.0, eps]
    if bps is not None: df["BPS(원)"] = [1000.0, 1000.0, bps]
    return df


def quarter_df(prev=(100.0, 10.0, 8.0), cur=(150.0, 20.0, 12.0), roe=9.5, est_rows=1):
    idx = pd.to_datetime(["2026-03-01", "2026-06-01", "2026-09-01"])
    df = pd.DataFrame({"매출액": [90.0, prev[0], cur[0]], "영업이익": [9.0, prev[1], cur[1]],
                       "당기순이익": [7.0, prev[2], cur[2]], "ROE(%)": [8.0, 9.0, roe]}, index=idx)
    if est_rows:   # 미래 추정치 행: 영업이익이 비어 있다 → 제외되어야 한다
        df.loc[pd.Timestamp("2026-12-01")] = [999.0, float("nan"), 999.0, 99.0]
    return df


class ShadowingTests(unittest.TestCase):
    def test_script_dir_removed_from_import_path(self):
        # scripts/calendar.py 가 표준 calendar 를 가리지 않도록 모듈이 자기 폴더를 경로에서 뺀다
        here = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
        self.assertNotIn(here, [os.path.abspath(p or os.getcwd()) for p in sys.path])

    def test_third_party_import_works_when_run_like_actions(self):
        # Actions 와 같은 방식(python scripts/multifactor_kr.py)으로 시작해도 FinanceDataReader 가 import 되는지: 새 프로세스에서 확인
        import subprocess
        scripts = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
        code = ("import runpy,sys; sys.path.insert(0, %r); m = runpy.run_path(%r, run_name='probe'); "
                "import requests, FinanceDataReader; print('IMPORT_OK')") % (scripts, os.path.join(scripts, "multifactor_kr.py"))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertIn("IMPORT_OK", r.stdout, r.stderr[-400:])


class RankTests(unittest.TestCase):
    def test_avg_rank_pct_multiples_of_ten_for_n10(self):
        vals = list(range(10, 0, -1))
        self.assertEqual([round(x, 6) for x in mf.avg_rank_pct(vals, True)], [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])

    def test_lower_is_better(self):
        self.assertEqual([round(x, 1) for x in mf.avg_rank_pct([5.0, 10.0, 20.0], False)], [33.3, 66.7, 100.0])

    def test_ties_get_average_rank_like_pandas(self):
        # 공동 1등 둘 → 1.5위, 그 아래는 3위 (책의 미국 표에서 보이는 2.5 와 같은 방식)
        self.assertEqual([round(x, 4) for x in mf.avg_rank_pct([3.0, 3.0, 1.0], True)], [50.0, 50.0, 100.0])

    def test_matches_pandas_rank_average(self):
        vals = [4.0, 1.0, 4.0, 9.0, 1.0, 7.0, 4.0]
        want = (pd.Series(vals).rank(ascending=False) / len(vals) * 100).tolist()
        got = mf.avg_rank_pct(vals, True)
        for g, w in zip(got, want): self.assertAlmostEqual(g, w, places=9)

    def test_book_composite_example(self):
        ranks = dict(zip(mf.FACTORS, [40, 50, 60, 50, 60, 50, 20, 10]))   # 책 표 2-8 삼성전자
        self.assertAlmostEqual(mf.composite(ranks, mf.FACTORS), 42.5)

    def test_book_value_growth_example(self):
        ranks = {"per": 22, "pbr": 44, "roe": 24, "rev": 9, "op": 12, "ni": 30, "mom_price": 57, "mom_vol": 3}
        self.assertAlmostEqual(mf.composite(ranks, mf.STYLES["value_growth"]["factors"]), 23.5)

    def test_style_factor_sets(self):
        s = mf.STYLES
        self.assertEqual(len(s["base"]["factors"]), 8)
        self.assertEqual(set(s["value_growth"]["factors"]), {"per", "pbr", "roe", "rev", "op", "ni"})
        self.assertEqual(set(s["trend_growth"]["factors"]), {"mom_price", "mom_vol", "roe", "rev", "op", "ni"})
        self.assertEqual(set(s["contrarian"]["factors"]), {"mom_price", "mom_vol", "per", "pbr"})

    def test_median(self):
        self.assertEqual(mf.median([3, 1, 2]), 2)
        self.assertEqual(mf.median([4, 1, 2, 3]), 2.5)
        self.assertIsNone(mf.median([]))


def mk_items(n=6, **over):
    """간단한 가짜 종목: 지표 값은 i 에 비례(클수록 좋음, PER·PBR 은 작을수록 좋음). over 로 지표별 값 목록을 덮어쓴다."""
    items = []
    for i in range(n):
        raw = {"mom_price": float(i), "mom_vol": float(i), "per": float(n - i), "pbr": float(n - i),
               "rev": float(i), "op": float(i), "ni": float(i), "roe": float(i)}
        for k, v in over.items(): raw[k] = v[i]
        items.append({"code": "%03d0" % i, "name": "종목%d" % i, "marcap": 1e12 - i, "raw": raw, "flags": []})
    return items


class ScoreTests(unittest.TestCase):
    def test_best_item_ranks_first_in_every_style(self):
        items = mf.score_items(mk_items(6))
        for st in mf.STYLES: self.assertEqual(items[5]["scores"][st]["rank"], 1.0, st)
        self.assertEqual(items[0]["scores"]["base"]["rank"], 6.0)

    def test_missing_value_is_filled_with_median_and_flagged(self):
        # 종목 2 의 ROE 가 비어 있으면 나머지 값의 중앙값으로 채워 순위를 매긴다(최하위가 아님)
        its = mf.score_items(mk_items(5, roe=[0.0, 1.0, None, 3.0, 4.0]))
        self.assertIn("roe", its[2]["filled"])
        self.assertIn("filled:roe", its[2]["flags"])
        # 값 [0,1,3,4] 의 중앙값 2.0 → 채운 값 2.0 은 0,1 보다 크고 3,4 보다 작다 → 큰 값이 좋으므로 3번째 순위(60%)
        self.assertAlmostEqual(its[2]["ranks"]["roe"], 60.0, places=1)

    def test_nonpositive_per_is_worst_by_default_but_best_in_strict(self):
        its = mf.score_items(mk_items(4, per=[-5.0, 10.0, 20.0, 30.0]))
        self.assertEqual(its[0]["ranks"]["per"], 100.0)                  # 적자는 최하위
        strict = mf.score_items(mk_items(4, per=[-5.0, 10.0, 20.0, 30.0]), strict=True)
        self.assertEqual(strict[0]["ranks"]["per"], 25.0)                # 패키지 방식: 음수가 가장 작은 값이라 1등

    def test_loss_company_with_empty_per_is_worst_not_median(self):
        # 적자 기업은 PER 이 빈 값으로 온다. 중앙값으로 채우면 중간 순위를 받으므로 per_loss 표시가 있으면 최하위로 둔다
        its = mk_items(4, per=[None, 10.0, 20.0, 30.0])
        its[0]["flags"].append("per_loss")
        out = mf.score_items(its)
        self.assertEqual(out[0]["ranks"]["per"], 100.0)
        self.assertNotIn("per", out[0]["filled"]); self.assertNotIn("filled:per", out[0]["flags"])

    def test_empty_per_without_loss_flag_is_median_filled(self):
        out = mf.score_items(mk_items(4, per=[None, 10.0, 20.0, 30.0]))
        self.assertIn("per", out[0]["filled"])
        self.assertLess(out[0]["ranks"]["per"], 100.0)

    def test_strict_ignores_loss_flag_and_fills_median_like_book(self):
        its = mk_items(4, per=[None, 10.0, 20.0, 30.0])
        its[0]["flags"].append("per_loss")
        out = mf.score_items(its, strict=True)
        self.assertIn("per", out[0]["filled"])
        self.assertLess(out[0]["ranks"]["per"], 100.0)

    def test_two_nonpositive_per_share_worst_average_rank(self):
        its = mf.score_items(mk_items(4, per=[-5.0, -1.0, 20.0, 30.0]))
        self.assertEqual(its[0]["ranks"]["per"], its[1]["ranks"]["per"])
        self.assertEqual(its[0]["ranks"]["per"], 87.5)

    def test_ties_in_composite_get_average_rank(self):
        same = [1.0, 1.0, 1.0]
        its = mf.score_items(mk_items(3, mom_price=same, mom_vol=same, per=same, pbr=same, rev=same, op=same, ni=same, roe=same))
        for it in its: self.assertEqual(it["scores"]["base"]["rank"], 2.0)   # 셋 다 동점 → 평균 2위

    def test_ranks_use_unrounded_values(self):
        # 소수 셋째 자리에서만 다른 값이 반올림 때문에 동점이 되면 안 된다(책 패키지와 순위가 어긋났던 원인)
        its = mf.score_items(mk_items(3, mom_vol=[1.001, 1.002, 1.003]))
        self.assertEqual([it["ranks"]["mom_vol"] for it in its], [100.0, 66.67, 33.33])


class GrowthTests(unittest.TestCase):
    def test_normal_growth(self):
        g, f = mf.growth_pct(150.0, 100.0)
        self.assertAlmostEqual(g, 50.0)
        self.assertIsNone(f)

    def test_negative_base_uses_abs_and_flags(self):
        g, f = mf.growth_pct(10.0, -10.0)      # 적자 → 흑자: 개선이므로 양수여야 한다
        self.assertAlmostEqual(g, 200.0)
        self.assertEqual(f, "base_nonpositive")

    def test_strict_negative_base_flips_sign_like_book(self):
        g, f = mf.growth_pct(10.0, -10.0, strict=True)
        self.assertAlmostEqual(g, -200.0)
        self.assertEqual(f, "base_nonpositive")

    def test_zero_or_missing_base(self):
        self.assertEqual(mf.growth_pct(5.0, 0.0), (None, None))
        self.assertEqual(mf.growth_pct(None, 5.0), (None, None))


class MetricsTests(unittest.TestCase):
    def test_metrics_values(self):
        m, flags, reason = mf.compute_metrics(price_df(), annual_df(per=12.0, pbr=1.5), quarter_df())
        self.assertIsNone(reason)
        self.assertEqual(m["per"], 12.0)
        self.assertEqual(m["pbr"], 1.5)
        self.assertAlmostEqual(m["rev"], 50.0)
        self.assertAlmostEqual(m["op"], 100.0)
        self.assertAlmostEqual(m["ni"], 50.0)
        self.assertEqual(m["roe"], 9.5)                       # 추정치 행(영업이익 없음)은 무시하고 마지막 확정 분기 사용
        self.assertEqual(m["_quarter_date"], "2026-09-01")
        self.assertEqual(m["mom_vol"], 0.0)                   # 거래량 일정 → 5일/20일 비율 0%
        self.assertGreater(m["mom_price"], 0)                 # 꾸준한 상승 → 양수

    def test_price_formula_matches_book_package(self):
        # 패키지 방식: 전일·주간·월간·3개월·연간 5개 기간(iloc[-2,-5,-20,-60,-240]) 등락률의 평균
        df = price_df()
        c = df["Close"]
        expect = sum((c.iloc[-1] / c.iloc[-k] - 1) * 100 for k in (2, 5, 20, 60, 240)) / 5
        m, _, _ = mf.compute_metrics(df, annual_df(), quarter_df())
        self.assertAlmostEqual(m["mom_price"], expect, places=9)

    def test_text_variant_uses_four_periods(self):
        old = mf.MOM_VARIANT
        try:
            mf.MOM_VARIANT = "text"
            df = price_df()
            c = df["Close"]
            expect = sum((c.iloc[-1] / c.iloc[-k] - 1) * 100 for k in (2, 6, 21, 241)) / 4
            m, _, _ = mf.compute_metrics(df, annual_df(), quarter_df())
            self.assertAlmostEqual(m["mom_price"], expect, places=9)
        finally:
            mf.MOM_VARIANT = old

    def test_short_history_uses_available_periods_and_flags(self):
        # 상장 100거래일: 3개월(60)까지는 있고 연간(240)은 없다 → 있는 4개 기간만 평균(패키지 방식)
        df = price_df(n=100)
        c = df["Close"]
        expect = sum((c.iloc[-1] / c.iloc[-k] - 1) * 100 for k in (2, 5, 20, 60)) / 4
        m, flags, reason = mf.compute_metrics(df, annual_df(), quarter_df())
        self.assertIsNone(reason)
        self.assertAlmostEqual(m["mom_price"], expect, places=9)
        self.assertIn("short_history", flags)

    def test_too_new_listing_dropped(self):
        _, _, reason = mf.compute_metrics(price_df(n=15), annual_df(), quarter_df())
        self.assertIn("20거래일 미만", reason)

    def test_zero_volume_average_gives_none_not_crash(self):
        m, _, reason = mf.compute_metrics(price_df(vol=0), annual_df(), quarter_df())
        self.assertIsNone(reason)
        self.assertIsNone(m["mom_vol"])

    def test_raw_values_are_not_rounded(self):
        m, _, _ = mf.compute_metrics(price_df(), annual_df(per=12.3456), quarter_df())
        self.assertEqual(m["per"], 12.3456)

    def test_loss_company_flags_per(self):
        m, flags, reason = mf.compute_metrics(price_df(), annual_df(per=-5.0), quarter_df())
        self.assertIsNone(reason)
        self.assertIn("per_unavailable", flags)

    def test_nan_per_with_negative_eps_flags_loss(self):
        a = annual_df(eps=-7497.0)
        a["PER(배)"] = float("nan")                      # 적자 기업: PER 은 빈 값, EPS 는 음수(삼성SDI·LG화학 실제 모습)
        m, flags, _ = mf.compute_metrics(price_df(), a, quarter_df())
        self.assertIsNone(m["per"]); self.assertIn("per_loss", flags)

    def test_nan_per_with_positive_eps_is_not_loss(self):
        a = annual_df(eps=500.0)
        a["PER(배)"] = float("nan")
        m, flags, _ = mf.compute_metrics(price_df(), a, quarter_df())
        self.assertNotIn("per_loss", flags)

    def test_nan_pbr_with_nonpositive_bps_flags_loss(self):
        a = annual_df(bps=-10.0)
        a["PBR(배)"] = float("nan")
        _, flags, _ = mf.compute_metrics(price_df(), a, quarter_df())
        self.assertIn("pbr_loss", flags)

    def test_nan_never_leaks_into_metrics(self):
        a = annual_df()
        a["PER(배)"] = float("nan")
        m, flags, _ = mf.compute_metrics(price_df(), a, quarter_df())
        self.assertIsNone(m["per"])
        json.dumps({k: v for k, v in m.items() if not k.startswith("_")}, allow_nan=False)   # NaN/inf 가 있으면 예외

    def test_negative_previous_quarter_flag(self):
        m, flags, _ = mf.compute_metrics(price_df(), annual_df(), quarter_df(prev=(100.0, -10.0, -5.0), cur=(100.0, 10.0, 5.0)))
        self.assertIn("base_nonpositive", flags)
        self.assertGreater(m["op"], 0)

    def test_strict_mode_reproduces_book_sign_flip(self):
        # 패키지의 pct_change: 적자(-10) → 흑자(+10) 는 (10-(-10))/(-10) = -200% 로 나온다
        q = quarter_df(prev=(100.0, -10.0, -5.0), cur=(100.0, 10.0, 5.0))
        m, _, _ = mf.compute_metrics(price_df(), annual_df(), q, strict=True)
        self.assertAlmostEqual(m["op"], -200.0)
        self.assertAlmostEqual(m["ni"], -200.0)


class UniverseTests(unittest.TestCase):
    def rows(self):
        base = dict(market="KOSPI", dept="", close=50000.0, volume=100000, marcap=5e12)
        return [dict(base, code="005930", name="삼성전자", marcap=9e14),
                dict(base, code="005935", name="삼성전자우", marcap=8e14),
                dict(base, code="000660", name="SK하이닉스", marcap=7e14),
                dict(base, code="111110", name="제1호스팩"),
                dict(base, code="222220", name="롯데리츠"),
                dict(base, code="333330", name="OO벤처투자"),
                dict(base, code="444440", name="소형주", marcap=5e10),
                dict(base, code="555550", name="동전주", close=500.0),
                dict(base, code="666660", name="코넥스사", market="KONEX"),
                dict(base, code="777770", name="코스닥사", market="KOSDAQ", marcap=1e12),
                dict(base, code="888880", name="저유동성", volume=1500),
                dict(base, code="099990", name="맥쿼리인프라"),
                dict(base, code="100000", name="메리츠금융지주", marcap=6e14),
                dict(base, code="196170", name="알테오젠", market="KOSDAQ GLOBAL", marcap=5e14)]

    def test_exclusions_and_order(self):
        keep, ex = mf.pre_filter(self.rows(), 20)
        self.assertEqual([r["name"] for r in keep], ["삼성전자", "SK하이닉스", "메리츠금융지주", "알테오젠", "코스닥사"])
        self.assertEqual(ex.get("우선주"), 1)
        self.assertEqual(ex.get("소형주(시총 1천억 미만)"), 1)
        self.assertEqual(ex.get("동전주(1천 원 미만)"), 1)
        self.assertEqual(ex.get("시장(코넥스 등)"), 1)
        self.assertEqual(ex.get("저유동성(당일 거래량 2천 주 미만)"), 1)
        self.assertEqual(ex.get("스팩·리츠·인프라·벤처 등(이름)"), 4)    # 스팩, 롯데리츠, 벤처투자, 맥쿼리인프라

    def test_merits_is_not_a_reit(self):
        # '메리츠' 안의 '리츠' 때문에 시총 수십조 원의 지주회사가 빠지면 안 된다(책 패키지는 이 오류가 있다)
        self.assertFalse(mf.name_excluded("메리츠금융지주"))
        self.assertFalse(mf.name_excluded("메리츠화재"))
        self.assertTrue(mf.name_excluded("롯데리츠"))
        self.assertTrue(mf.name_excluded("이리츠코크렙"))
        self.assertTrue(mf.name_excluded("맥쿼리인프라"))
        self.assertTrue(mf.name_excluded("제5호스팩"))

    def test_kosdaq_global_included_by_default_excluded_in_strict(self):
        keep, _ = mf.pre_filter(self.rows(), 20)
        self.assertIn("196170", [r["code"] for r in keep])
        keep_s, _ = mf.pre_filter(self.rows(), 20, strict=True)
        self.assertNotIn("196170", [r["code"] for r in keep_s])
        self.assertNotIn("100000", [r["code"] for r in keep_s])     # strict 는 메리츠도 패키지처럼 제외

    def test_preferred_rule_is_last_char_5_7_9_K(self):
        base = dict(market="KOSPI", dept="", close=50000.0, volume=100000, marcap=5e12)
        rows = [dict(base, code=c, name="X" + c) for c in ("005930", "005935", "000157", "000159", "00104K", "0000J0", "123456")]
        kept = [r["code"] for r in mf.pre_filter(rows, 10)[0]]
        self.assertEqual(sorted(kept), sorted(["005930", "0000J0", "123456"]))

    def test_top_n_cut(self):
        keep, _ = mf.pre_filter(self.rows(), 2)
        self.assertEqual([r["code"] for r in keep], ["005930", "000660"])

    def test_method_info_lists_deviations(self):
        m = mf.method_info(False)
        self.assertEqual(m["momentum"]["variant"], "library")
        self.assertEqual(len(m["momentum"]["periods"]), 5)
        self.assertGreaterEqual(len(m["deviations"]), 5)
        self.assertEqual(mf.method_info(True)["deviations"], [])


class FakeFetcher:
    version = "fake"

    def __init__(self, rows, fail=lambda code: False, per_by_code=None):
        self.rows, self.fail, self.per_by_code = rows, fail, per_by_code or {}

    def listing(self): return self.rows

    def _chk(self, code):
        if self.fail(code): raise TimeoutError("timeout")

    def price(self, code): self._chk(code); return price_df(step=0.1 + int(code[:3]) / 1000.0)
    def annual(self, code): self._chk(code); return annual_df(per=self.per_by_code.get(code, 10.0))
    def quarter(self, code): self._chk(code); return quarter_df()


def make_rows(n):
    return [dict(code="%03d000" % (i + 1), name="종목%d" % (i + 1), market="KOSPI", dept="", close=50000.0,
                 volume=100000, marcap=1e13 - i * 1e10) for i in range(n)]


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "mf.json")
        self.log = []

    def test_end_to_end_output(self):
        f = FakeFetcher(make_rows(12), per_by_code={"001000": -4.0})
        code = mf.run(f, 12, self.out, sleep=0, log=self.log.append)
        self.assertEqual(code, 0)
        d = json.loads(_r(self.out))
        self.assertEqual(d["schema"], "multifactor_kr/1")
        self.assertEqual(d["n"], 12)
        self.assertEqual(set(d["styles"]), {"base", "value_growth", "trend_growth", "contrarian"})
        ranks = [it["scores"]["base"]["rank"] for it in d["items"]]
        self.assertEqual(ranks, sorted(ranks))                       # 기본 순위 오름차순으로 저장
        loss = [it for it in d["items"] if it["code"] == "001000"][0]
        self.assertIn("per_unavailable", loss["flags"])
        self.assertEqual(loss["ranks"]["per"], 100.0)                 # 적자 종목은 PER 최하위
        for it in d["items"]:
            self.assertEqual(set(it["ranks"]), set(mf.FACTORS))
            for st in d["styles"]: self.assertIn(st, it["scores"])
            for v in it["raw"].values():                              # 저장값은 표시용으로 소수 둘째 자리까지
                if v is not None: self.assertEqual(v, round(v, 2))
        self.assertEqual(d["method"]["momentum"]["variant"], "library")
        json.dumps(d, allow_nan=False)

    def test_consecutive_failures_abort_and_preserve_existing_file(self):
        _w(self.out, '{"keep":"me"}')
        f = FakeFetcher(make_rows(30), fail=lambda c: int(c[:3]) > 5)  # 6번째부터 계속 실패
        code = mf.run(f, 30, self.out, sleep=0, log=self.log.append)
        self.assertEqual(code, 3)
        self.assertEqual(_r(self.out), '{"keep":"me"}')

    def test_too_few_ok_does_not_overwrite(self):
        _w(self.out, '{"keep":"me"}')
        f = FakeFetcher(make_rows(20), fail=lambda c: int(c[:3]) % 2 == 0)  # 절반 실패(연속은 아님)
        code = mf.run(f, 20, self.out, sleep=0, log=self.log.append)
        self.assertEqual(code, 3)
        self.assertEqual(_r(self.out), '{"keep":"me"}')

    def test_isolated_failures_are_recorded_but_ok(self):
        f = FakeFetcher(make_rows(20), fail=lambda c: c in ("003000", "011000"))
        code = mf.run(f, 20, self.out, sleep=0, log=self.log.append)
        self.assertEqual(code, 0)
        d = json.loads(_r(self.out))
        self.assertEqual(d["n"], 18)
        self.assertEqual({x["code"] for x in d["universe"]["failed"]}, {"003000", "011000"})

    def test_strict_flag_is_recorded(self):
        f = FakeFetcher(make_rows(12))
        self.assertEqual(mf.run(f, 12, self.out, sleep=0, log=self.log.append, strict=True), 0)
        d = json.loads(_r(self.out))
        self.assertTrue(d["method"]["strict_book"])
        self.assertEqual(d["method"]["deviations"], [])


if __name__ == "__main__":
    unittest.main()
