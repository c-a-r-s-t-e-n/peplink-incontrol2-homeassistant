"""Tests cover GPS freshness and diagnostics without importing Home Assistant."""

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "peplink_incontrol2"


def load(filename, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gps = load("gps.py", "test_gps_pure")
localization = load("localization.py", "test_diagnostic_i18n")


class GPSTests(unittest.TestCase):
    now = datetime(2026, 11, 10, 20, 0, tzinfo=timezone.utc)

    def test_live_online_point(self):
        # Berlin is UTC+1 during November.
        value = gps.location_info(
            {"la": 50.0, "lo": 8.0, "ts": "2026-11-10T20:58:00", "isStatic": False},
            "Europe/Berlin", online=True, now=self.now,
        )
        self.assertTrue(value["is_current"])
        self.assertEqual(value["measured_at"], "2026-11-10T19:58:00+00:00")

    def test_old_offline_point_is_historical(self):
        value = gps.location_info(
            {"la": 50.0, "lo": 8.0, "ts": "2026-11-02T12:00:00"},
            "Europe/Berlin", online=False, now=self.now,
        )
        self.assertFalse(value["is_current"])
        self.assertEqual(value["latitude"], 50.0)

    def test_old_online_position_not_current(self):
        value = gps.location_info(
            {"la": 50.0, "lo": 8.0, "ts": "2026-11-10T20:00:00"},
            "Europe/Berlin", online=True, now=self.now,
        )
        self.assertFalse(value["is_current"])

    def test_static_and_invalid_positions_rejected(self):
        self.assertIsNone(gps.location_info({"la": 50, "lo": 8, "ts": "2026-11-10T20:00:00", "isStatic": True}))
        self.assertIsNone(gps.location_info({"la": 999, "lo": 8, "ts": "2026-11-10T20:00:00"}))
        self.assertIsNone(gps.location_info({"la": 50, "lo": 8, "ts": "bad"}))


class DiagnosticTests(unittest.TestCase):
    def test_localized_survey_no_reports(self):
        self.assertEqual(localization.diagnostic_label("survey_empty", "de"), "Kein Site Survey vorhanden")
        self.assertEqual(localization.diagnostic_label("survey_empty", "en"), "No site survey recorded")

    def test_unknown_locale_falls_back_to_english(self):
        self.assertEqual(localization.diagnostic_label("wan_ok", "fr"), "Cellular measurements available")


if __name__ == "__main__":
    unittest.main()
