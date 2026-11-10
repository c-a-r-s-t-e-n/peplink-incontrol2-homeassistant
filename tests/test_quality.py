"""Tests use synthetic records based on sanitized response field names."""

import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "custom_components" / "peplink_incontrol2" / "quality.py"
spec = importlib.util.spec_from_file_location("quality", MODULE)
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


class CellularQualityTest(unittest.TestCase):
    def test_ignore_non_cellular_wan_with_newer_timestamp(self):
        reports = {
            "1": {"name": "Ethernet", "stat": [{"ts": 200, "type": "WAN"}]},
            "2": {"name": "Cellular", "stat": [
                {"ts": 100, "rsrp": -70, "rsrq": -9, "rssi": -41, "sinr": 24, "band": "LTE Band 3", "bearer": "LTE"}
            ]},
        }
        sample, name = quality.latest_cellular_sample(reports, "rsrp")
        self.assertEqual(sample["rsrp"], -70)
        self.assertEqual(name, "Cellular")

    def test_5g_report_available_without_live_modem(self):
        reports = {"2": {"name": "5G", "stat": [
            {"ts": 100, "rsrp": -85, "rsrq": -12, "rssi": -72,
             "sinr": 23, "band": "5G Band n78", "bearer": "5G"}
        ]}}
        sample, _ = quality.latest_cellular_sample(reports, "band")
        self.assertEqual(sample["band"], "5G Band n78")

    def test_missing_carrier_stays_unknown(self):
        reports = {"2": {"name": "Cellular", "stat": [{"ts": 100, "rsrp": -70}]}}
        self.assertEqual(quality.latest_cellular_sample(reports, "carrier_name"), (None, None))

    def test_select_field_from_older_valid_sample(self):
        reports = {"2": {"name": "Cellular", "stat": [
            {"ts": 100, "rsrp": -80, "carrier_name": "provider"},
            {"ts": 110, "rsrp": -75}
        ]}}
        sample, _ = quality.latest_cellular_sample(reports, "carrier_name")
        self.assertEqual(sample["ts"], 100)

    def test_empty_data(self):
        self.assertEqual(quality.latest_cellular_sample({}), (None, None))


if __name__ == "__main__":
    unittest.main()
