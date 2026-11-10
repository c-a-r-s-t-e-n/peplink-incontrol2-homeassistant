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

                            quality_by_wan = dict(details.get("wan_quality_by_wan", {}))
                            quality_dates = _as_list(details.get("wan_quality_dates"))
                            days = sorted(
                                [v["day"] for v in quality_dates if isinstance(v, dict) and isinstance(v.get("day"), str)],
                                reverse=True,
                            )
                            quality_day = days[0] if days else today
                            quality_start = quality_day + "T00:00:00"
                            quality_end = (now_str if quality_day == today else quality_day + "T23:59:59")

                            for wid in _wan_ids(device, details):
                                result = await self._optional(path + "/wan_quality", {
                                    "wan_id": wid,
                                    "start": quality_start,
                                    "end": quality_end,
                                })
                                if isinstance(result, dict) and isinstance(result.get("stat"), list):
                                    interface = next(
                                        (i for i in _as_list(device.get("interfaces"))
                                         if isinstance(i, dict) and str(i.get("id")) == str(wid)),
                                        {},
                                    )
                                    quality_by_wan[str(wid)] = {
                                        "name": interface.get("name", f"WAN {wid}"),
                                        "stat": result["stat"],
                                    }
                            details["wan_quality_by_wan"] = quality_by_wan
                            available = [
                                x for x in quality_by_wan.values()
                                if isinstance(x, dict) and x.get("stat")
                            ]
                            if available:
                                newest = max(
                                    available,
                                    key=lambda x: max(
                                        (s.get("ts") or 0 for s in x["stat"] if isinstance(s, dict)),
                                        default=0,
                                    ),
                                )
                                details["wan_quality"] = {"stat": newest["stat"]}
                                details["wan_quality_wan_name"] = newest.get("name")

                            details["report_last_requested"] = now_str
                        self._detail_cache[key] = details
                        devices[key] = {
                            "device": device, "detail": details, "organization": oid,
                            "group": gid, "org_name": org.get("name"),
                        }
            return devices
        except (IC2Error, KeyError, TypeError, ValueError) as exc:
            raise UpdateFailed("Cannot update Peplink device inventory") from exc
