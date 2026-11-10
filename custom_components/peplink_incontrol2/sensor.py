"""Reported inventory, network and diagnostic values; unavailable values remain unknown."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from .const import DOMAIN
from .entity import PeplinkEntity
from .quality import latest_cellular_sample

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
}

async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    entities = [PeplinkSensor(c, k, field) for k in c.data for field in (*FIELDS, *EXTRA)]
    for key, item in c.data.items():
        seen_ids = set()
        for interface in item.get("device", {}).get("interfaces", []):
            if not isinstance(interface, dict) or interface.get("id") is None:
                continue
            identifier = str(interface["id"])
            if identifier in seen_ids:
                continue
            seen_ids.add(identifier)
            entities.append(PeplinkInterfaceStatus(c, key, identifier, interface.get("name")))
    async_add_entities(entities)

class PeplinkSensor(PeplinkEntity, SensorEntity):
    def __init__(self, coordinator, key, field):
        super().__init__(coordinator, key)
        self.field = field
        name, unit = (FIELDS | EXTRA)[field]
        self._attr_name = name
        self._attr_unique_id = key + "_" + field
        if unit:
            self._attr_native_unit_of_measurement = unit
        if field in ("fw_ver", "prime_expiry_date", "expiry_date"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        field = self.field
        if field in FIELDS:
            return self.device_data.get(field)
        d = self.detail
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
        if field in ("gps_speed", "gps_altitude"):
            loc = d.get("location")
            if not isinstance(loc, dict):
                return None
            value = loc.get("speed_kph" if field == "gps_speed" else "at")
            return value if isinstance(value, (float, int)) else None
        if field in ("tower_count", "tower_latest"):
            x = d.get("tower_scans")
            reports = (x.get("id") if isinstance(x, dict) else x) or []
            if isinstance(reports, dict):
                reports = [reports]
            if not isinstance(reports, list) or not reports:
                return None
            latest = reports[0] if isinstance(reports[0], dict) else {}
            cells = latest.get("cellular_tower_scan")
            return (len(cells) if isinstance(cells, list) else None) if field == "tower_count" else latest.get("start_date")
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
            if report is not None:
                return "Report returned"
            dates = d.get("tower_dates")
            if isinstance(dates, list) and not dates:
                return "No survey dates reported"
            return "No survey report available"
        if field == "wan_signal_diagnostic":
            by_wan = d.get("wan_quality_by_wan")
            if not isinstance(by_wan, dict) or not by_wan:
                return "No WAN quality report returned"
            if any(isinstance(wan, dict) and wan.get("stat") for wan in by_wan.values()):
                sample, _ = self._best_wan_sample()
                return "Cellular fields available" if sample else "No cellular fields in samples"
            return "No WAN quality samples"
        if field.startswith("wan_") and field != "wan_outages":
            mapping = {"wan_quality_timestamp": "datetime",
                       "wan_cell_id": "cid", "wan_carrier": "carrier_name"}
            api_key = mapping.get(field, field.removeprefix("wan_"))
            sample, _ = self._best_wan_sample(api_key)
            if sample is None and field == "wan_quality_timestamp":
                quality = d.get("wan_quality")
                stats = quality.get("stat") if isinstance(quality, dict) else None
                if isinstance(stats, list):
                    valid = [v for v in stats if isinstance(v, dict)]
                    if valid:
                        sample = max(valid, key=lambda v: v.get("ts") or 0)
            return sample.get(api_key) if isinstance(sample, dict) else None
        if field == "gps_age":
            loc = d.get("location")
            if not isinstance(loc, dict):
                return None
            ts = loc.get("ts")
            if not ts:
                return None
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    try:
                        dt = dt.replace(tzinfo=ZoneInfo(self.device_data.get("group_timezone_label") or "UTC"))
                    except (ZoneInfoNotFoundError, KeyError):
                        return None
                age = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 60
                return round(age) if age >= -5 else None
            except (ValueError, TypeError):
                return None
        return None

    def _best_wan_sample(self, required=None):
        return latest_cellular_sample(self.detail.get("wan_quality_by_wan"), required)

    @property
    def extra_state_attributes(self):
        field = self.field
        if field.startswith("wan_") and field != "wan_outages":
            _, name = self._best_wan_sample()
            return {"wan_name": name, "report_day": self.detail.get("wan_quality_report_day")}
        if field == "last_event":
            x = self.detail.get("events")
            if isinstance(x, list) and x and isinstance(x[0], dict):
                return {"timestamp": x[0].get("ts"), "detail": str(x[0].get("detail", ""))[:255]}
        if field == "tower_count":
            x = self.detail.get("tower_scans")
            reports = (x.get("id") if isinstance(x, dict) else x) or []
            if isinstance(reports, list) and reports:
                cells = reports[0].get("cellular_tower_scan", [])
                if isinstance(cells, list):
                    return {"cells": [{k: cell.get(k) for k in ("carrier_name", "mobile_type", "band", "channel", "cell_id", "pci", "rsrp", "rsrq")}
                                       for cell in cells[:20] if isinstance(cell, dict)]}
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
                i for i in self.device_data.get("interfaces", [])
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
