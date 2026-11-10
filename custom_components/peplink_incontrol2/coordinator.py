"""Coordinate read-only InControl 2 device, interface, and historical reports."""

from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IC2Error
from .const import DOMAIN, DEFAULT_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _as_list(value):
    """Treat one API object and an array consistently."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _timezone(device):
    try:
        return ZoneInfo(device.get("group_timezone_label") or "UTC")
    except (ZoneInfoNotFoundError, KeyError, TypeError):
        return ZoneInfo("UTC")


def _wan_ids(device, details):
    """Collect WAN IDs returned by inventory/usage; never invent IDs."""
    values = []
    for item in _as_list(device.get("interfaces")):
        if isinstance(item, dict) and item.get("id") is not None:
            values.append(item["id"])
    for report_name in ("bandwidth_daily", "bandwidth_monthly", "wan_history"):
        report = details.get(report_name)
        if isinstance(report, dict):
            for item in _as_list(report.get("wans")):
                if isinstance(item, dict) and item.get("id") is not None:
                    values.append(item["id"])
    unique = []
    for value in values:
        try:
            wid = int(value)
        except (TypeError, ValueError):
            continue
        if wid > 0 and wid not in unique:
            unique.append(wid)
    return unique[:12]


class PeplinkCoordinator(DataUpdateCoordinator):
    """Share API polling across entities and maintain last valid reports."""

    def __init__(self, hass, client):
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_INTERVAL),
        )
        self.client = client
        self._round = 0
        self._detail_cache = {}

    async def _optional(self, path, params=None):
        try:
            return await self.client.get(path, params)
        except IC2Error as exc:
            _LOGGER.debug("Optional InControl endpoint %s unavailable: %s", path.rsplit("/", 1)[-1], exc)
            return None

    async def _async_update_data(self):
        try:
            orgs = _as_list(await self.client.get("/rest/o"))
            devices = {}
            self._round += 1

            for org in orgs:
                oid = org["id"]
                groups = _as_list(await self.client.get(f"/rest/o/{oid}/g"))
                for group in groups:
                    gid = group.get("id")
                    if gid is None:
                        continue
                    base = f"/rest/o/{oid}/g/{gid}"
                    items = await self._optional(base + "/d", {"has_status": "true"})
                    if not isinstance(items, list):
                        items = await self.client.get(base + "/d")
                    for device in _as_list(items):
                        if not isinstance(device, dict) or device.get("id") is None:
                            continue
                        did = device["id"]
                        key = f"{oid}_{gid}_{did}"
                        path = f"{base}/d/{did}"
                        details = dict(self._detail_cache.get(key, {}))

                        # Per-device endpoint can expose richer WAN interface data.
                        # Inventory remains the fallback if device detail is unavailable.
                        full_device = await self._optional(path)
                        if isinstance(full_device, dict):
                            device = {**device, **full_device}

                        location = await self._optional(path + "/loc")
                        if isinstance(location, dict):
                            details["location"] = location
                        elif isinstance(location, list) and location and isinstance(location[0], dict):
                            details["location"] = location[0]

                        # Historical reporting runs every 20 minutes, plus initial refresh.
                        if self._round == 1 or self._round % 10 == 0:
                            now = datetime.now(_timezone(device))
                            today = now.strftime("%Y-%m-%d")
                            now_str = now.strftime("%Y-%m-%dT%H:%M:%S")
                            midnight = today + "T00:00:00"
                            past_week = (now - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")
                            past_week_day = (now - timedelta(days=7)).strftime("%Y-%m-%d")

                            calls = {
                                "bandwidth_daily": ("/bandwidth", {"type": "daily"}),
                                "bandwidth_monthly": ("/bandwidth", {"type": "monthly"}),
                                "events": ("/event_log", None),
                                "availability": ("/availability", {"start": past_week, "end": now_str}),
                                "tower_dates": ("/cellular_tower_scan/results/dates", None),
                                "wan_quality_dates": ("/wan_quality/dates", None),
                                "wan_history": ("/wan_history", {"start": past_week_day, "end": today, "page": 1, "limit": 100}),
                            }
                            for name, (suffix, params) in calls.items():
                                output = await self._optional(path + suffix, params)
                                if output is not None:
                                    details[name] = output

                            # WAN history without wan_id often returns metadata only.
                            # Resolve each WAN independently, then combine history records.
                            history_metadata = details.get("wan_history")
                            history_ids = []
                            if isinstance(history_metadata, dict):
                                history_ids = [
                                    v.get("id") for v in _as_list(history_metadata.get("wans"))
                                    if isinstance(v, dict) and v.get("id") is not None
                                ]
                            histories = {}
                            for wan_id in history_ids[:8]:
                                try:
                                    numeric_id = int(wan_id)
                                except (ValueError, TypeError):
                                    continue
                                if numeric_id <= 0:
                                    continue
                                result = await self._optional(path + "/wan_history", {
                                    "wan_id": numeric_id, "start": past_week_day, "end": today,
                                    "page": 1, "limit": 100,
                                })
                                if isinstance(result, dict) and isinstance(result.get("status"), list):
                                    histories[str(numeric_id)] = result["status"]
                            if histories:
                                details["wan_history_by_wan"] = histories
                                details["wan_history"] = {
                                    "status": [item for records in histories.values() for item in records]
                                }

                            # A survey list requires an explicit date range.
                            # Prefer the most recently reported survey day.
                            scan_dates = _as_list(details.get("tower_dates"))
                            scan_days = sorted(
                                [v["day"] for v in scan_dates if isinstance(v, dict) and isinstance(v.get("day"), str)],
                                reverse=True,
                            )
                            if scan_days:
                                scan_day = scan_days[0]
                                result = await self._optional(
                                    path + "/cellular_tower_scan/results",
                                    {"start": scan_day + "T00:00:00", "end": scan_day + "T23:59:59"},
                                )
                                if result is not None:
                                    details["tower_scans"] = result

                            # The quality endpoint first returns the actual WAN list
                            # for the selected report day. Inventory interfaces are NOT
                            # guaranteed to use the same IDs or include every WAN.
                            quality_dates = _as_list(details.get("wan_quality_dates"))
                            days = sorted(
                                [row["day"] for row in quality_dates
                                 if isinstance(row, dict) and isinstance(row.get("day"), str)],
                                reverse=True,
                            )
                            quality_day = days[0] if days else today
                            quality_start = quality_day + "T00:00:00"
                            quality_end = now_str if quality_day == today else quality_day + "T23:59:59"
                            quality_params = {"start": quality_start, "end": quality_end}
                            quality_meta = await self._optional(path + "/wan_quality", quality_params)

                            # Prefer authoritative WAN IDs from the quality report.
                            # Fall back to inventory / bandwidth IDs only if absent.
                            reported_wans = (
                                quality_meta.get("wans", [])
                                if isinstance(quality_meta, dict) else []
                            )
                            if reported_wans:
                                candidates = [
                                    (wan.get("id"), wan.get("name"))
                                    for wan in reported_wans if isinstance(wan, dict)
                                ]
                            else:
                                candidates = [(wid, None) for wid in _wan_ids(device, details)]

                            quality_by_wan = {}
                            seen = set()
                            for raw_id, reported_name in candidates[:16]:
                                try:
                                    wid = int(raw_id)
                                except (TypeError, ValueError):
                                    continue
                                if wid <= 0 or wid in seen:
                                    continue
                                seen.add(wid)
                                result = await self._optional(path + "/wan_quality", {
                                    **quality_params, "wan_id": wid,
                                })
                                if not isinstance(result, dict) or not isinstance(result.get("stat"), list):
                                    continue
                                samples = [row for row in result["stat"] if isinstance(row, dict)]
                                # Reports may not arrive in chronological order.
                                def sample_key(row):
                                    try:
                                        stamp = float(row.get("ts"))
                                    except (TypeError, ValueError):
                                        stamp = 0.0
                                    return (stamp, str(row.get("datetime") or ""))

                                samples.sort(key=sample_key)
                                # These reports can contain tens of thousands of records.
                                # Keep only recent samples plus the newest cellular sample
                                # so stored coordinator state stays small.
                                signal_fields = (
                                    "rsrp", "rsrq", "sinr", "rssi", "band", "bearer",
                                    "carrier_name", "cid",
                                )
                                matching = [row for row in samples if any(
                                    row.get(field) is not None for field in signal_fields
                                )]
                                retained = samples[-3:] + matching[-12:]
                                unique_samples = []
                                seen_samples = set()
                                for row in retained:
                                    identity = (row.get("ts"), row.get("datetime"), row.get("wan_id"))
                                    if identity not in seen_samples:
                                        seen_samples.add(identity)
                                        unique_samples.append(row)
                                interface = next(
                                    (i for i in _as_list(device.get("interfaces"))
                                     if isinstance(i, dict) and str(i.get("id")) == str(wid)),
                                    {},
                                )
                                quality_by_wan[str(wid)] = {
                                    "name": reported_name or interface.get("name") or f"WAN {wid}",
                                    "stat": unique_samples,
                                }
                            # Replace old samples when a fresh report is received; never
                            # merge a previous day silently with the latest day's data.
                            if quality_by_wan:
                                details["wan_quality_by_wan"] = quality_by_wan
                                details["wan_quality_report_day"] = quality_day
                                available = [data for data in quality_by_wan.values() if data["stat"]]
                                if available:
                                    newest = max(
                                        available,
                                        key=lambda data: max(
                                            (str(row.get("ts") or "") for row in data["stat"]),
                                            default="",
                                        ),
                                    )
                                    details["wan_quality"] = {"stat": newest["stat"]}
                                    details["wan_quality_wan_name"] = newest["name"]

                            details["report_last_requested"] = now_str
                        self._detail_cache[key] = details
                        devices[key] = {
                            "device": device, "detail": details, "organization": oid,
                            "group": gid, "org_name": org.get("name"),
                        }
            return devices
        except (IC2Error, KeyError, TypeError, ValueError) as exc:
            raise UpdateFailed("Cannot update Peplink device inventory") from exc
