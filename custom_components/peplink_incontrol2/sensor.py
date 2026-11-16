"""Reported inventory, network and diagnostic values; unavailable values remain unknown."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import PeplinkEntity
from .gps import location_info
from .localization import diagnostic_label
from .quality import latest_cellular_sample, latest_survey, sample_key

FIELDS = {
    "status": ("Cloud status", None),
    "fw_ver": ("Firmware", None),
    "last_online": ("Last online", None),
    "uptime": ("Uptime", "s"),
    "pepvpn_peers": ("PepVPN peers", None),
    "client_count": ("Connected clients", None),
    "prime_expiry_date": ("Prime expiry", None),
    "expiry_date": ("Subscription expiry", None),
}

EXTRA = {
    "report_status": ("Report coverage", None),
    "report_last_requested": ("Reports last requested", None),
    "event_count": ("Event log entries", None),
    "last_event": ("Last event", None),
    "wan_outages": ("WAN history entries", None),
    "tower_count": ("Last survey cell count", None),
    "tower_latest": ("Last tower survey", None),
    "wan_rsrp": ("WAN RSRP latest", "dBm"),
    "wan_rsrq": ("WAN RSRQ latest", "dB"),
    "wan_sinr": ("WAN SINR latest", "dB"),
    "wan_rssi": ("WAN RSSI latest", "dBm"),
    "gps_age": ("GPS age", "min"),
    "gps_speed": ("GPS speed", "km/h"),
    "gps_altitude": ("GPS altitude", "m"),
    "availability_latest": ("Availability latest", "%"),
    "traffic_today_up": ("Daily upload", "MB"),
    "traffic_today_down": ("Daily download", "MB"),
    "traffic_month_up": ("Monthly upload", "MB"),
    "traffic_month_down": ("Monthly download", "MB"),
    "wan_carrier": ("WAN carrier latest", None),
    "wan_band": ("WAN band latest", None),
    "wan_cell_id": ("WAN cell ID latest", None),
    "wan_bearer": ("WAN bearer latest", None),
    "wan_quality_timestamp": ("WAN quality last sample", None),
    "wan_signal_diagnostic": ("WAN signal diagnostics", None),
    "tower_diagnostic": ("Tower survey diagnostics", None),
    "gps_last_seen": ("GPS last reported", None),
    "gps_position_fresh": ("GPS position current", None),
}


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    known = set()

    def discover():
        entities = []
        for key, item in (c.data or {}).items():
            for field in (*FIELDS, *EXTRA):
                identity = (key, field)
                if identity not in known:
                    known.add(identity)
                    entities.append(PeplinkSensor(c, key, field))
            for interface in item.get("device", {}).get("interfaces") or []:
                if not isinstance(interface, dict) or interface.get("id") is None:
                    continue
                identifier = str(interface["id"])
                identity = (key, "interface", identifier)
                if identity not in known:
                    known.add(identity)
                    entities.append(PeplinkInterfaceStatus(c, key, identifier, interface.get("name")))
            for wid, report in item.get("detail", {}).get("wan_quality_by_wan", {}).items():
                for field in ("lms", "rsrp", "rsrq", "sinr", "rssi"):
                    identity = (key, "quality", wid, field)
                    if identity not in known and any(
                        isinstance(r, dict) and r.get(field) is not None for r in report.get("stat", [])
                    ):
                        known.add(identity)
                        entities.append(PeplinkWanQuality(c, key, wid, field, report.get("name")))
        async_add_entities(entities)

    discover()
    entry.async_on_unload(c.async_add_listener(discover))


class PeplinkSensor(PeplinkEntity, SensorEntity):
    def __init__(self, coordinator, key, field):
        super().__init__(coordinator, key)
        self.field = field
        name, unit = (FIELDS | EXTRA)[field]
        self._attr_name = name
        self._attr_unique_id = key + "_" + field
        if unit:
            self._attr_native_unit_of_measurement = unit
        if field in (
            "fw_ver",
            "prime_expiry_date",
            "expiry_date",
            "report_status",
            "report_last_requested",
            "tower_diagnostic",
            "wan_signal_diagnostic",
        ):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        field = self.field
        if field in FIELDS:
            return self.device_data.get(field)
        d = self.detail
        if field == "report_status":
            return d.get(field, "waiting")
        if field == "report_last_requested":
            return d.get(field)
        if field == "event_count":
            x = d.get("events")
            return len(x) if isinstance(x, list) else None
        if field == "last_event":
            x = d.get("events")
            return x[0].get("event_type") if isinstance(x, list) and x and isinstance(x[0], dict) else None
        if field == "wan_outages":
            x = d.get("wan_history")
            by_wan = d.get("wan_history_by_wan")
            if isinstance(by_wan, dict):
                return sum(len(entries) for entries in by_wan.values() if isinstance(entries, list))
            return len(x.get("status", [])) if isinstance(x, dict) and isinstance(x.get("status"), list) else None
        if field == "availability_latest":
            records = d.get("availability")
            if isinstance(records, list) and records:
                last = records[-1]
                if isinstance(last, dict) and isinstance(last.get("internet_availability"), (float, int)):
                    raw = last["internet_availability"]
                    return round(raw * 100 if raw <= 1 else raw, 2)
            return None
        if field == "gps_last_seen":
            point = self._gps_info()
            return point["measured_at"] if point else None
        if field == "gps_position_fresh":
            point = self._gps_info()
            return "yes" if point and point["is_current"] else "no"
        if field in ("gps_speed", "gps_altitude"):
            loc = d.get("location")
            if not isinstance(loc, dict):
                return None
            value = loc.get("speed_kph" if field == "gps_speed" else "at")
            return (
                (round(value, 2) if field == "gps_speed" else round(value, 1))
                if isinstance(value, (float, int))
                else None
            )
        if field in ("tower_count", "tower_latest"):
            latest = latest_survey(d.get("tower_scans"))
            if latest is None:
                return None
            cells = latest.get("cellular_tower_scan")
            return (
                (len(cells) if isinstance(cells, list) else None)
                if field == "tower_count"
                else latest.get("start_date")
            )
        if field.startswith("traffic_"):
            report = d.get("bandwidth_daily" if "today" in field else "bandwidth_monthly")
            if not isinstance(report, dict):
                return None
            usages = report.get("Usages") or report.get("usages")
            if not isinstance(usages, list) or not usages:
                return None
            try:
                local_tz = ZoneInfo(self.device_data.get("group_timezone_label") or "UTC")
            except (ZoneInfoNotFoundError, KeyError):
                local_tz = timezone.utc
            period = datetime.now(local_tz).strftime("%Y-%m-%d" if "today" in field else "%Y-%m")
            records = [u for u in usages if isinstance(u, dict) and str(u.get("from_date", "")).startswith(period)]
            if not records:
                return None
            # Daily/monthly endpoint reports period totals; avoid summing duplicates.
            record = max(records, key=lambda u: str(u.get("from_date", "")))
            v = record.get("up" if field.endswith("up") else "down")
            return round(float(v), 2) if isinstance(v, (float, int)) else None
        if field == "tower_diagnostic":
            report = d.get("tower_scans")
            dates = d.get("tower_dates")
            if latest_survey(report) is not None:
                code = "survey_report"
            elif report == {"id": []} or (isinstance(dates, list) and len(dates) == 0):
                code = "survey_empty"
            else:
                code = "survey_missing"
            return diagnostic_label(code, self.hass.config.language)
        if field == "wan_signal_diagnostic":
            by_wan = d.get("wan_quality_by_wan")
            if not isinstance(by_wan, dict) or not by_wan:
                code = "wan_missing"
            elif not any(isinstance(item, dict) and item.get("stat") for item in by_wan.values()):
                code = "wan_empty"
            else:
                sample, _ = self._best_wan_sample()
                code = "wan_ok" if sample else "wan_no_signal"
            return diagnostic_label(code, self.hass.config.language)
        if field.startswith("wan_") and field != "wan_outages":
            mapping = {"wan_quality_timestamp": "datetime", "wan_cell_id": "cid", "wan_carrier": "carrier_name"}
            api_key = mapping.get(field, field.removeprefix("wan_"))
            sample, _ = self._best_wan_sample(api_key)
            if sample is None and field == "wan_quality_timestamp":
                quality = d.get("wan_quality")
                stats = quality.get("stat") if isinstance(quality, dict) else None
                if isinstance(stats, list):
                    valid = [v for v in stats if isinstance(v, dict)]
                    if valid:
                        sample = max(valid, key=sample_key)
            return sample.get(api_key) if isinstance(sample, dict) else None
        if field == "gps_age":
            point = self._gps_info()
            return point["age_minutes"] if point else None
        return None

    def _gps_info(self):
        return location_info(
            self.detail.get("location"),
            self.device_data.get("group_timezone_label") or "UTC",
            online=str(self.device_data.get("status", "")).lower() == "online",
        )

    def _best_wan_sample(self, required=None):
        return latest_cellular_sample(self.detail.get("wan_quality_by_wan"), required)

    @property
    def extra_state_attributes(self):
        field = self.field
        if field.startswith("wan_") and field != "wan_outages":
            mapping = {"wan_quality_timestamp": "datetime", "wan_cell_id": "cid", "wan_carrier": "carrier_name"}
            sample, name = self._best_wan_sample(mapping.get(field, field.removeprefix("wan_")))
            sample = sample or {}
            return {
                "wan_name": name,
                "report_day": self.detail.get("wan_quality_report_day"),
                "sample_time": sample.get("datetime"),
                "sample_epoch": sample.get("ts"),
                "historical": True,
            }
        if field == "last_event":
            x = self.detail.get("events")
            if isinstance(x, list) and x and isinstance(x[0], dict):
                return {"timestamp": x[0].get("ts"), "detail": str(x[0].get("detail", ""))[:255]}
        if field == "tower_count":
            report = latest_survey(self.detail.get("tower_scans"))
            cells = report.get("cellular_tower_scan") if report else None
            if isinstance(cells, list):
                return {
                    "cells": [
                        {
                            k: cell.get(k)
                            for k in (
                                "carrier_name",
                                "mobile_type",
                                "band",
                                "channel",
                                "cell_id",
                                "pci",
                                "rsrp",
                                "rsrq",
                            )
                        }
                        for cell in cells[:20]
                        if isinstance(cell, dict)
                    ]
                }
        return None


class PeplinkInterfaceStatus(PeplinkEntity, SensorEntity):
    """Per-WAN status from the device inventory, not an inferred ping result."""

    def __init__(self, coordinator, key, interface_id, display_name):
        super().__init__(coordinator, key)
        self.interface_id = interface_id
        self._attr_unique_id = f"{key}_wan_{interface_id}_status"
        self._attr_name = f"{display_name or 'WAN ' + interface_id} status"

    @property
    def _interface(self):
        return next(
            (
                i
                for i in (self.device_data.get("interfaces") or [])
                if isinstance(i, dict) and str(i.get("id")) == self.interface_id
            ),
            {},
        )

    @property
    def native_value(self):
        return self._interface.get("status")

    @property
    def extra_state_attributes(self):
        i = self._interface
        # No public IP, SIM ID or subscriber identifiers in state attributes.
        return {
            "interface_type": i.get("type"),
            "connection_mode": i.get("conn_mode"),
            "healthcheck": i.get("healthcheck"),
            "enabled": i.get("enable"),
            "last_status_change": i.get("updated_at"),
        }


class PeplinkWanQuality(PeplinkEntity, SensorEntity):
    """Historical per-WAN measurements using the same shared cloud report."""

    def __init__(self, coordinator, key, wan_id, field, name):
        super().__init__(coordinator, key)
        self.wan_id, self.field = wan_id, field
        self._attr_unique_id = f"{key}_quality_{wan_id}_{field}"
        self._attr_name = f"{name or 'WAN ' + wan_id} {('latency' if field == 'lms' else field.upper())} latest"
        self._attr_native_unit_of_measurement = "ms" if field == "lms" else "dBm" if field in ("rsrp", "rssi") else "dB"
        self._attr_device_class = SensorDeviceClass.DURATION if field == "lms" else SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_state_class = SensorStateClass.MEASUREMENT

    def _sample(self):
        rows = self.detail.get("wan_quality_by_wan", {}).get(self.wan_id, {}).get("stat", [])
        return max(
            (
                r
                for r in rows
                if isinstance(r.get(self.field), (float, int)) and not isinstance(r.get(self.field), bool)
            ),
            key=sample_key,
            default={},
        )

    @property
    def native_value(self):
        return self._sample().get(self.field)

    @property
    def extra_state_attributes(self):
        sample = self._sample()
        return {
            "sample_time": sample.get("datetime"),
            "sample_epoch": sample.get("ts"),
            "report_day": self.detail.get("wan_quality_report_day"),
            "historical": True,
        }
