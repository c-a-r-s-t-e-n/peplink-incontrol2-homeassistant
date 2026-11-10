"""Reported inventory, network and diagnostic values; unavailable values remain unknown."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from .const import DOMAIN
from .entity import PeplinkEntity

FIELDS = {
    "status": ("Cloud status", None),
    "fw_ver": ("Firmware", None),
    "last_online": ("Last online", None),
    "uptime": ("Uptime", "s"),
    "pepvpn_peers": ("PepVPN peers", None),
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
    "traffic_today_up": ("Daily upload", "MB"),
    "traffic_today_down": ("Daily download", "MB"),
    "traffic_month_up": ("Monthly upload", "MB"),
    "traffic_month_down": ("Monthly download", "MB"),
    "wan_carrier": ("WAN carrier latest", None),
    "wan_band": ("WAN band latest", None),
    "wan_cell_id": ("WAN cell ID latest", None),
    "wan_bearer": ("WAN bearer latest", None),
    "wan_quality_timestamp": ("WAN quality last sample", None),
}

async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PeplinkSensor(c, k, field) for k in c.data for field in (*FIELDS, *EXTRA)])

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
            return len(x.get("status", [])) if isinstance(x, dict) and isinstance(x.get("status"), list) else None
        if field in ("tower_count", "tower_latest"):
            x = d.get("tower_scans")
            reports = (x.get("id") if isinstance(x, dict) else x) or []
            if not isinstance(reports, list) or not reports:
                return None
            return len(reports[0].get("cellular_tower_scan", [])) if field == "tower_count" else reports[0].get("start_date")
        if field.startswith("traffic_"):
            report = d.get("bandwidth_daily" if "today" in field else "bandwidth_monthly")
            if not isinstance(report, dict):
                return None
            usages = report.get("Usages") or report.get("usages")
            if not isinstance(usages, list) or not usages:
                return None
            from datetime import datetime
            period = datetime.now().strftime("%Y-%m-%d" if "today" in field else "%Y-%m")
            records = [u for u in usages if isinstance(u, dict) and str(u.get("from_date", "")).startswith(period)]
            if not records:
                return None
            # Daily/monthly endpoint reports period totals; avoid summing duplicates.
            record = max(records, key=lambda u: str(u.get("from_date", "")))
            v = record.get("up" if field.endswith("up") else "down")
            return round(float(v), 2) if isinstance(v, (float, int)) else None
        if field.startswith("wan_") and field not in ("wan_outages",):
            quality = d.get("wan_quality")
            if not isinstance(quality, dict):
                return None
            stat = quality.get("stat")
            if not isinstance(stat, list) or not stat:
                return None
            fieldmap = {"wan_quality_timestamp": "datetime", "wan_cell_id": "cid", "wan_carrier": "carrier_name"}
            api_field = fieldmap.get(field, field.removeprefix("wan_"))
            sample = max((s for s in stat if isinstance(s, dict)), key=lambda s: s.get("ts") or 0, default={})
            return sample.get(api_field)
        if field == "gps_age":
            from datetime import datetime, timezone
            loc = d.get("location")
            if not isinstance(loc, dict):
                return None
            ts = loc.get("ts")
            if not ts:
                return None
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    # InControl reports times in group-local time; avoid inaccurate age
                    return None
                return round(max(0, (datetime.now(timezone.utc) - dt).total_seconds() / 60))
            except (ValueError, TypeError):
                return None
        return None

    @property
    def extra_state_attributes(self):
        field = self.field
        if field.startswith("wan_") and field != "wan_outages":
            return {"wan_name": self.detail.get("wan_quality_wan_name")}
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
