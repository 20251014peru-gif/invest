"""kr_investor.py 시험 — 가짜 KRX(stock) 로 목표일 규칙·휴장 건너뛰기·실패 처리·건너뛰기 규칙을 검사한다. 실제 KRX 호출 없음.
사용: python3 -m unittest tests/test_kr_investor.py   (pandas 필요)"""
import datetime as dt, json, sys, tempfile, unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import kr_investor as k

KST = k.KST
IDX = ['금융투자', '보험', '투신', '사모', '은행', '기타금융', '연기금 등', '기관합계', '기타법인', '개인', '외국인', '기타외국인', '전체']


def frame(ext=-2000.0, inst=500.0, per=-300.0, other_corp=1800.0, other_ext=0.0):
    """억원 단위 입력 → 원 단위 DataFrame. 기관 세부는 기관합계가 되도록 첫 칸에 몰아준다."""
    v = {i: 0.0 for i in IDX}
    v.update({'금융투자': inst, '기관합계': inst, '기타법인': other_corp, '개인': per, '외국인': ext, '기타외국인': other_ext})
    v['전체'] = 0.0
    return pd.DataFrame({'매도': 0.0, '매수': 0.0, '순매수': [v[i] * 1e8 for i in IDX]}, index=IDX)


class Fake:
    def __init__(self, data=None, fail=None):
        self.data, self.fail, self.calls = data or {}, fail, []

    def get_market_trading_value_by_investor(self, a, b, m):
        self.calls.append((a, m))
        if self.fail:
            raise self.fail
        return self.data.get((a, m), pd.DataFrame())


def at(y, m, d, h=8):
    return dt.datetime(y, m, d, h, 0, tzinfo=KST)


class TargetDay(unittest.TestCase):
    def test_morning_uses_previous_weekday(self):
        self.assertEqual(k.target_day(at(2026, 10, 2, 8)), dt.date(2026, 10, 1))   # 금 아침 → 목
        self.assertEqual(k.target_day(at(2026, 10, 5, 8)), dt.date(2026, 10, 2))   # 월 아침 → 금

    def test_after_close_uses_today(self):
        self.assertEqual(k.target_day(at(2026, 10, 2, 18)), dt.date(2026, 10, 2))
        self.assertEqual(k.target_day(at(2026, 10, 2, 15)), dt.date(2026, 10, 1))   # 마감 직후 15시는 아직 확정 아님

    def test_weekend_goes_to_friday(self):
        self.assertEqual(k.target_day(at(2026, 10, 3, 20)), dt.date(2026, 10, 2))   # 토
        self.assertEqual(k.target_day(at(2026, 10, 4, 9)), dt.date(2026, 10, 2))    # 일


class Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = str(Path(self.tmp) / 'facts' / 'kr_investor.json')
        self.st = str(Path(self.tmp) / 'data' / 'status.json')

    def go(self, stock, now):
        return k.run(now=now, stock=stock, out=self.out, status_path=self.st)

    def data(self, *dates):
        d = {}
        for ds in dates:
            d[(ds, 'KOSPI')] = frame()
            d[(ds, 'KOSDAQ')] = frame(ext=-100.0, inst=50.0, per=50.0, other_corp=0.0)
        return d

    def test_ok_values_and_sum_check(self):
        rc = self.go(Fake(self.data('20261001', '20260930')), at(2026, 10, 2, 8))
        self.assertEqual(rc, 0)
        o = json.load(open(self.out, encoding='utf-8'))
        self.assertEqual((o['status'], o['base_date'], o['target']), ('ok', '2026-10-01', '2026-10-01'))
        kp = o['days'][0]['KOSPI']
        self.assertEqual((kp['외국인'], kp['기관합계'], kp['개인']), (-2000.0, 500.0, -300.0))
        self.assertEqual(kp['합계검사'], 0.0)
        self.assertEqual(kp['기관세부차'], 0.0)
        self.assertEqual(len(o['days']), 2)
        job = [j for j in json.load(open(self.st, encoding='utf-8'))['jobs'] if j['id'] == 'kr_investor'][0]
        self.assertEqual((job['status'], job['note']), ('ok', '기준일 2026-10-01'))

    def test_holiday_is_skipped(self):
        f = Fake(self.data('20260930', '20260929'))          # 10/1 은 빈 결과(휴장)
        self.assertEqual(self.go(f, at(2026, 10, 2, 8)), 0)
        o = json.load(open(self.out, encoding='utf-8'))
        self.assertEqual(o['base_date'], '2026-09-30')
        self.assertEqual(o['target'], '2026-10-01')           # 목표일과 기준일이 다름이 그대로 남는다

    def test_second_run_same_target_does_not_call_krx(self):
        f = Fake(self.data('20261001', '20260930'))
        self.go(f, at(2026, 10, 2, 8)); n = len(f.calls)
        self.assertEqual(self.go(f, at(2026, 10, 2, 9)), 0)
        self.assertEqual(len(f.calls), n)

    def test_failure_keeps_old_values_but_marks_fail(self):
        self.go(Fake(self.data('20261001', '20260930')), at(2026, 10, 2, 8))
        rc = self.go(Fake(fail=RuntimeError('login blocked')), at(2026, 10, 5, 8))
        self.assertEqual(rc, 1)
        o = json.load(open(self.out, encoding='utf-8'))
        self.assertEqual((o['status'], o['base_date'], o['target']), ('fail', '2026-10-01', '2026-10-02'))
        self.assertIn('login blocked', o['error'])
        job = [j for j in json.load(open(self.st, encoding='utf-8'))['jobs'] if j['id'] == 'kr_investor'][0]
        self.assertEqual(job['status'], 'fail')

    def test_all_empty_is_failure_not_zero(self):
        self.assertEqual(self.go(Fake({}), at(2026, 10, 2, 8)), 1)
        o = json.load(open(self.out, encoding='utf-8'))
        self.assertEqual((o['status'], o['days']), ('fail', []))

    def test_one_market_empty_is_error(self):
        d = {('20261001', 'KOSPI'): frame()}
        self.assertEqual(self.go(Fake(d), at(2026, 10, 2, 8)), 1)

    def test_retry_after_failure_even_same_target(self):
        self.go(Fake(fail=RuntimeError('x')), at(2026, 10, 2, 8))
        f = Fake(self.data('20261001', '20260930'))
        self.assertEqual(self.go(f, at(2026, 10, 2, 9)), 0)
        self.assertEqual(json.load(open(self.out, encoding='utf-8'))['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
