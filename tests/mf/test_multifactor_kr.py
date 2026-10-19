# -*- coding: utf-8 -*-
"""multifactor_kr 단위 시험 — 네트워크 없이 가짜 데이터로 검증한다.
실행: python -m unittest discover -s tests/mf -p "test_*.py" -v
책(2장)의 예시값을 재현한다: 순위 8개 [40,50,60,50,60,50,20,10] 의 평균 = 42.5,
가치 성장 예시(PER 22, PBR 44, ROE 24, 매출 9, 영업이익 12, 순이익 30) 의 평균 = 23.5(책 표에는 반올림 24).
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


def annual_df(per=10.0, pbr=1.0):
    idx = pd.to_datetime(["2023-12-01", "2024-12-01", "2025-12-01"])
    return pd.DataFrame({"PER(배)": [8.0, 9.0, per], "PBR(배)": [0.8, 0.9, pbr], "영업이익": [1.0, 2.0, 3.0]}, index=idx)


def quarter_df(prev=(100.0, 10.0, 8.0), cur=(150.0, 20.0, 12.0), roe=9.5, est_rows=1):
    idx = pd.to_datetime(["2026-03-01", "2026-06-01", "2026-09-01"])
    df = pd.DataFrame({"매출액": [90.0, prev[0], cur[0]], "영업이익": [9.0, prev[1], cur[1]],
                       "당기순이익": [7.0, prev[2], cur[2]], "ROE(%)": [8.0, 9.0, roe]}, index=idx)
    if est_rows:   # 미래 추정치 행: 영업이익이 비어 있다 → 제외되어야 한다
        df.loc[pd.Timestamp("2026-12-01")] = [999.0, float("nan"), 999.0, 99.0]
    return df


class RankTests(unittest.TestCase):
    def test_rank_pct_multiples_of_ten_for_n10(self):
        vals = list(range(10, 0, -1))
        self.assertEqual(mf.rank_pct(vals, True), [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])

    def test_lower_is_better_for_per(self):
        self.assertEqual(mf.rank_pct([5.0, 10.0, 20.0], False), [33.3, 66.7, 100.0])

    def test_per_nonpositive_and_none_are_worst(self):
        out = mf.rank_pct([5.0, -3.0, None, 20.0], False, bad=lambda v: v <= 0)
        self.assertEqual(out[0], 25.0)            # 5.0 이 1등
        self.assertEqual(out[3], 50.0)            # 20.0 이 2등
        self.assertEqual(out[1], out[2])          # 적자(-3)와 없음(None)은 같은 최하위
        self.assertEqual(out[1], 75.0)

    def test_ties_share_best_rank(self):
        self.assertEqual(mf.rank_pct([3.0, 3.0, 1.0], True), [33.3, 33.3, 100.0])

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


class GrowthTests(unittest.TestCase):
    def test_normal_growth(self):
        g, f = mf.growth_pct(150.0, 100.0)
        self.assertAlmostEqual(g, 50.0); self.assertIsNone(f)

    def test_negative_base_uses_abs_and_flags(self):
        g, f = mf.growth_pct(10.0, -10.0)      # 적자 → 흑자: 개선이므로 양수여야 한다
        self.assertAlmostEqual(g, 200.0); self.assertEqual(f, "base_nonpositive")

    def test_zero_or_missing_base(self):
        self.assertEqual(mf.growth_pct(5.0, 0.0), (None, None))
        self.assertEqual(mf.growth_pct(None, 5.0), (None, None))


class MetricsTests(unittest.TestCase):
    def test_metrics_values(self):
        m, flags, reason = mf.compute_metrics(price_df(), annual_df(per=12.0, pbr=1.5), quarter_df())
        self.assertIsNone(reason)
        self.assertEqual(m["per"], 12.0); self.assertEqual(m["pbr"], 1.5)
        self.assertAlmostEqual(m["rev"], 50.0); self.assertAlmostEqual(m["op"], 100.0); self.assertAlmostEqual(m["ni"], 50.0)
        self.assertEqual(m["roe"], 9.5)                       # 추정치 행(영업이익 없음)은 무시하고 마지막 확정 분기 사용
        self.assertEqual(m["_quarter_date"], "2026-09-01")
        self.assertEqual(m["mom_vol"], 0.0)                   # 거래량 일정 → 5일/20일 비율 0%
        self.assertGreater(m["mom_price"], 0)                 # 꾸준한 상승 → 양수

    def test_price_formula_matches_book_definition(self):
        df = price_df()
        c = df["Close"]
        expect = sum((c.iloc[-1] / c.iloc[-k] - 1) * 100 for k in (2, 6, 21, 241)) / 4
        m, _, _ = mf.compute_metrics(df, annual_df(), quarter_df())
        self.assertAlmostEqual(m["mom_price"], round(expect, 2), places=2)

    def test_short_history_dropped(self):
        _, _, reason = mf.compute_metrics(price_df(n=200), annual_df(), quarter_df())
        self.assertIn("1년 미만", reason)

    def test_low_liquidity_dropped(self):
        _, _, reason = mf.compute_metrics(price_df(vol=1500), annual_df(), quarter_df())
        self.assertIn("저유동성", reason)

    def test_loss_company_flags_per(self):
        m, flags, reason = mf.compute_metrics(price_df(), annual_df(per=-5.0), quarter_df())
        self.assertIsNone(reason); self.assertIn("per_unavailable", flags)

    def test_nan_never_leaks_into_metrics(self):
        a = annual_df(); a["PER(배)"] = float("nan")
        m, flags, _ = mf.compute_metrics(price_df(), a, quarter_df())
        self.assertIsNone(m["per"])
        json.dumps(m, allow_nan=False)                         # NaN/inf 가 있으면 예외

    def test_negative_previous_quarter_flag(self):
        m, flags, _ = mf.compute_metrics(price_df(), annual_df(), quarter_df(prev=(100.0, -10.0, -5.0), cur=(100.0, 10.0, 5.0)))
        self.assertIn("base_nonpositive", flags); self.assertGreater(m["op"], 0)


class UniverseTests(unittest.TestCase):
    def rows(self):
        base = dict(market="KOSPI", dept="", close=50000.0, volume=100000, marcap=5e12)
        return [dict(base, code="005930", name="삼성전자", marcap=9e14),
                dict(base, code="005935", name="삼성전자우", marcap=8e14),
                dict(base, code="000660", name="SK하이닉스", marcap=7e14),
                dict(base, code="111110", name="제1호스팩", dept="SPAC(소속부없음)"),
                dict(base, code="222220", name="롯데리츠"),
                dict(base, code="333330", name="OO벤처투자"),
                dict(base, code="444440", name="소형주", marcap=5e10),
                dict(base, code="555550", name="동전주", close=500.0),
                dict(base, code="666660", name="코넥스사", market="KONEX"),
                dict(base, code="777770", name="코스닥사", market="KOSDAQ", marcap=1e12)]

    def test_exclusions_and_order(self):
        keep, ex = mf.pre_filter(self.rows(), 10)
        self.assertEqual([r["code"] for r in keep], ["005930", "000660", "777770"])
        for reason in ("우선주", "스팩", "리츠", "벤처투자사(이름 근사)", "소형주(시총 1천억 미만)", "동전주(1천 원 미만)", "시장(코넥스 등)"):
            self.assertEqual(ex.get(reason), 1, reason)

    def test_top_n_cut(self):
        keep, _ = mf.pre_filter(self.rows(), 2)
        self.assertEqual([r["code"] for r in keep], ["005930", "000660"])


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
        self.tmp = tempfile.mkdtemp(); self.out = os.path.join(self.tmp, "mf.json")
        self.log = []

    def test_end_to_end_output(self):
        f = FakeFetcher(make_rows(12), per_by_code={"001000": -4.0})
        code = mf.run(f, 12, self.out, sleep=0, log=self.log.append)
        self.assertEqual(code, 0)
        d = json.loads(_r(self.out))
        self.assertEqual(d["schema"], "multifactor_kr/1"); self.assertEqual(d["n"], 12)
        self.assertEqual(set(d["styles"]), {"base", "value_growth", "trend_growth", "contrarian"})
        ranks = [it["scores"]["base"]["rank"] for it in d["items"]]
        self.assertEqual(ranks, sorted(ranks))                       # 기본 순위 오름차순으로 저장
        loss = [it for it in d["items"] if it["code"] == "001000"][0]
        self.assertIn("per_unavailable", loss["flags"])
        self.assertEqual(loss["ranks"]["per"], 100.0)                 # 적자 종목은 PER 최하위
        for it in d["items"]:
            self.assertEqual(set(it["ranks"]), set(mf.FACTORS))
            for st in d["styles"]: self.assertIn(st, it["scores"])
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
        self.assertEqual(d["n"], 18); self.assertEqual({x["code"] for x in d["universe"]["failed"]}, {"003000", "011000"})


if __name__ == "__main__":
    unittest.main()
