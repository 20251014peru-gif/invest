import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class MacroExtraConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "data" / "macro_extra_indicators.json").read_text(encoding="utf-8"))

    def test_required_market_gear_series_are_configured_once(self):
        items = self.config["items"]
        ids = [item["id"] for item in items]
        self.assertEqual(len(ids), len(set(ids)))
        expected = {
            "us30y": ("DGS30", "%"),
            "us_hy_oas": ("BAMLH0A0HYM2", "%p"),
            "us_ccc_oas": ("BAMLH0A3HYC", "%p"),
            "sofr": ("SOFR", "%"),
        }
        by_id = {item["id"]: item for item in items}
        for item_id, (symbol, unit) in expected.items():
            self.assertIn(item_id, by_id)
            self.assertEqual(by_id[item_id]["symbol"], symbol)
            self.assertEqual(by_id[item_id]["unit"], unit)
            self.assertEqual(by_id[item_id]["cycle"], "D")
            self.assertTrue(by_id[item_id]["official"])
            self.assertGreater(by_id[item_id]["max_age_days"], 0)

    def test_usdkrw_remains_official_ecos_series(self):
        config = json.loads((ROOT / "data" / "indicators.json").read_text(encoding="utf-8"))
        usdkrw = next(item for item in config["items"] if item["id"] == "usdkrw")
        self.assertEqual(usdkrw["source"], "ecos")
        self.assertEqual(usdkrw["ecos"]["stat"], "731Y001")
        self.assertEqual(usdkrw["ecos"]["item"], "0000001")
        self.assertEqual(usdkrw["ecos"]["cycle"], "D")


if __name__ == "__main__":
    unittest.main()
