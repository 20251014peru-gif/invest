# -*- coding: utf-8 -*-
"""verify.py 의 순수 로직 시험(네트워크·키 없이). 실행: python -m unittest discover -s tests/mf_verify -p "test_*.py" -v"""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import verify as v


def row(sj, aid, nm, th="1,000", add="2,000"):
    return {"sj_div": sj, "account_id": aid, "account_nm": nm, "thstrm_amount": th, "thstrm_add_amount": add}


class PickTests(unittest.TestCase):
    def test_pick_by_standard_id_first(self):
        rows = [row("IS", "-표준계정코드 미사용-", "매출액", "5"), row("IS", "ifrs-full_Revenue", "수익(매출액)", "1,234,000,000")]
        val, acc = v.pick_amount(rows, "rev", "thstrm_amount")
        self.assertEqual(val, 1234000000.0)
        self.assertEqual(acc[0], "ifrs-full_Revenue")

    def test_fallback_to_account_name(self):
        rows = [row("IS", "-표준계정코드 미사용-", "영업이익(손실)", "-500")]
        val, acc = v.pick_amount(rows, "op", "thstrm_amount")
        self.assertEqual(val, -500.0)
        self.assertEqual(acc[1], "영업이익(손실)")

    def test_ignores_balance_sheet_rows(self):
        rows = [row("BS", "ifrs-full_Revenue", "매출액", "999")]
        self.assertEqual(v.pick_amount(rows, "rev", "thstrm_amount"), (None, None))

    def test_cis_rows_are_searched_too(self):
        rows = [row("CIS", "ifrs-full_ProfitLoss", "분기순이익", "7")]
        self.assertEqual(v.pick_amount(rows, "ni", "thstrm_amount")[0], 7.0)

    def test_cumulative_field(self):
        rows = [row("IS", "dart_OperatingIncomeLoss", "영업이익", "10", "25")]
        self.assertEqual(v.pick_amount(rows, "op", "thstrm_add_amount")[0], 25.0)

    def test_missing_or_bad_amount(self):
        rows = [row("IS", "ifrs-full_Revenue", "매출액", "-", "-")]
        self.assertEqual(v.pick_amount(rows, "rev", "thstrm_amount"), (None, None))


class CompareTests(unittest.TestCase):
    def test_won_to_eok_tolerance(self):
        self.assertTrue(v.close_enough(1000.0, 1000.4 * 1e8))     # 반올림 수준 차이
        self.assertFalse(v.close_enough(1000.0, 1100.0 * 1e8))    # 10% 차이
        self.assertTrue(v.close_enough(100000.0, 100200.0 * 1e8))  # 0.2% 는 상대 허용오차 안
        self.assertIsNone(v.close_enough(None, 1e8))
        self.assertIsNone(v.close_enough(10.0, None))

    def test_to_num(self):
        self.assertEqual(v.to_num("1,234"), 1234.0)
        self.assertEqual(v.to_num("-12"), -12.0)
        self.assertIsNone(v.to_num("-"))
        self.assertIsNone(v.to_num(None))


class QuarterLogicTests(unittest.TestCase):
    def test_fourth_quarter_is_annual_minus_nine_month_cumulative(self):
        calls = []
        def fake_fetch(corp, year, reprt):
            calls.append(reprt)
            if reprt == "11011": return [row("IS", "ifrs-full_Revenue", "매출액", "1,000", "1,000")], "CFS", None
            if reprt == "11014": return [row("IS", "ifrs-full_Revenue", "매출액", "250", "700")], "CFS", None
            return None, None, "unexpected"
        old = v.fetch_statement
        try:
            v.fetch_statement = fake_fetch
            vals, accs, fs, err = v.quarter_amounts("00126380", 2025, 4)
        finally:
            v.fetch_statement = old
        self.assertIsNone(err)
        self.assertEqual(vals["rev"], 300.0)          # 1000 - 700
        self.assertEqual(sorted(calls), ["11011", "11014"])

    def test_quarter_uses_three_month_amount_of_matching_report(self):
        seen = []
        def fake_fetch(corp, year, reprt):
            seen.append(reprt)
            return [row("IS", "dart_OperatingIncomeLoss", "영업이익", "40", "90")], "CFS", None
        old = v.fetch_statement
        try:
            v.fetch_statement = fake_fetch
            vals, _, _, _ = v.quarter_amounts("1", 2026, 2)
        finally:
            v.fetch_statement = old
        self.assertEqual(seen, ["11012"])             # 2분기 = 반기보고서
        self.assertEqual(vals["op"], 40.0)            # 누적(90)이 아니라 3개월 금액

    def test_key_is_never_part_of_errors(self):
        os.environ["DART_API_KEY"] = "SECRETKEY123"
        d, err = v.http_json("fnlttSinglAcntAll.json", {"corp_code": "1"})   # 네트워크 없이도/있어도 키가 결과에 나오면 안 된다
        self.assertNotIn("SECRETKEY123", str(d) + str(err))
        os.environ.pop("DART_API_KEY", None)


if __name__ == "__main__":
    unittest.main()
