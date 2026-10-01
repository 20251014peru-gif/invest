import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import report_feeds as f
from macro import parse_yahoo_bars


class FeedTests(unittest.TestCase):
    def test_missing_holiday_is_not_zero_or_forward_filled(self):
        raw = b'observation_date,SP500\n2026-09-25,100\n2026-09-28,.\n2026-09-29,101\n'
        rows = f.normalized(f.parse_fred(raw, 'SP500'), dt.date(2026, 10, 1))
        self.assertEqual([x['date'] for x in rows], ['2026-09-25', '2026-09-29'])

    def test_wrong_fred_series_rejected(self):
        with self.assertRaises(f.DataError):
            f.parse_fred(b'observation_date,NDX\n2026-09-30,10\n', 'NASDAQCOM')

    def test_conflicting_date_rejected(self):
        with self.assertRaises(f.DataError):
            f.normalized([('2026-09-29', 1), ('2026-09-29', 2)], dt.date(2026, 10, 1))

    def test_future_and_nonfinite_rejected(self):
        for bad in [('2026-10-02', 1), ('2026-09-30', float('nan'))]:
            with self.subTest(bad=bad), self.assertRaises(f.DataError):
                f.normalized([('2026-09-29', 1), bad], dt.date(2026, 10, 1))

    def test_two_dates_required(self):
        with self.assertRaises(f.DataError):
            f.normalized([('2026-09-29', 1)], dt.date(2026, 10, 1))

    def test_wrong_fx_close_definition_rejected(self):
        spec = dict(stat='731Y003', item='0000003', item_name='원/달러(종가 15:30)', source_unit='원')
        row = dict(STAT_CODE='731Y003', ITEM_CODE1='0000003', ITEM_NAME1='원/달러(종가)', UNIT_NAME='원', TIME='20260930', DATA_VALUE='1352.8')
        with self.assertRaises(f.DataError):
            f.parse_ecos(json.dumps({'StatisticSearch': {'row': [row]}}).encode(), spec)
        row['ITEM_NAME1'] = spec['item_name']
        self.assertEqual(f.parse_ecos(json.dumps({'StatisticSearch': {'row': [row]}}).encode(), spec), [('2026-09-30', '1352.8')])

    def test_nyfed_does_not_mix_rates(self):
        with self.assertRaises(f.DataError):
            f.parse_nyfed(b'{"refRates":[{"type":"OBFR","effectiveDate":"2026-09-30","percentRate":4}]}', 'EFFR')

    def test_bp_and_raw_provenance(self):
        spec = dict(id='test', label='test', group='test', definition='yield', unit='%', price_type='yield', source_url='https://example.org', provider='fred', series='X', change_unit='bp')
        response = ([('2026-09-29', 4.0), ('2026-09-30', 4.03)], b'raw', 'https://example.org', 'fred_csv', [])
        with tempfile.TemporaryDirectory() as tmp, patch.object(f, 'fetch', return_value=response):
            result = f.collect_one(spec, {}, Path(tmp))
            self.assertEqual(result['change'], 3.0)
            self.assertEqual(result['observation_date'], '2026-09-30')
            self.assertEqual(result['previous_observation_date'], '2026-09-29')
            self.assertEqual(len(result['raw_sha256']), 64)
            self.assertFalse(result['signal_eligible'])

    def test_error_does_not_leak_secret_or_retain_value(self):
        spec = dict(id='test', label='test', group='test', definition='test', unit='%', price_type='test', source_url='https://example.org', provider='fred', change_unit='%')
        with tempfile.TemporaryDirectory() as tmp, patch.object(f, 'fetch', side_effect=RuntimeError('api_key=TOP_SECRET')):
            result = f.collect_one(spec, {}, Path(tmp))
        self.assertNotIn('TOP_SECRET', json.dumps(result))
        self.assertIsNone(result['value'])
        self.assertEqual(result['connection_status'], 'error')

    def test_yahoo_uses_actual_exchange_dates_not_today(self):
        times = [int(dt.datetime(2026, 9, d, 13, 30, tzinfo=dt.timezone.utc).timestamp()) for d in (25, 28)]
        payload = {'chart': {'result': [{'meta': {'exchangeTimezoneName': 'America/New_York', 'regularMarketPrice': 999, 'chartPreviousClose': 888}, 'timestamp': times, 'indicators': {'quote': [{'close': [100, 102]}]}}]}}
        self.assertEqual(parse_yahoo_bars(payload), [('2026-09-25', 100.0), ('2026-09-28', 102.0)])

    def test_registry_preserves_ids_and_no_cross_product_fallback(self):
        root = Path(__file__).resolve().parents[1]
        cfg = json.loads((root / 'data/report_feed_registry.json').read_text(encoding='utf-8'))
        self.assertEqual(len(cfg['items']), 23)
        self.assertEqual(len(set(i['id'] for i in cfg['items'])), 23)
        self.assertEqual(sum(i['provider'] == 'blocked' for i in cfg['items']), 6)
        old = json.loads((root / 'data/indicators.json').read_text(encoding='utf-8'))
        wti = next(i for i in old['items'] if i['id'] == 'wti')
        self.assertNotIn('fred_fallback', wti)

    def test_overnight_overlap_preserves_quote_but_withholds_comparison(self):
        times = [int(dt.datetime(2026, 9, 30, hour, tzinfo=dt.timezone.utc).timestamp()) for hour in (0, 2)]
        payload = {'chart': {'result': [{'meta': {'exchangeTimezoneName': 'America/New_York'}, 'timestamp': times, 'indicators': {'quote': [{'close': [90, 91]}]}}]}}
        self.assertEqual(parse_yahoo_bars(payload), [('2026-09-29', 91.0)])
        payload['chart']['result'][0]['timestamp'] = [times[0], times[0]]
        with self.assertRaises(RuntimeError):
            parse_yahoo_bars(payload)


if __name__ == '__main__':
    unittest.main()
