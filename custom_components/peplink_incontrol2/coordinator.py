"""Coordinate read-only InControl 2 device, interface, and historical reports."""

import logging
from datetime import datetime, timedelta, timezone
from time import monotonic
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IC2AuthError, IC2Error, IC2RateLimitError
from .const import DEFAULT_INTERVAL, DOMAIN
from .quality import latest_survey, retain_samples, sample_key

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

    def __init__(self, hass, client, entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_INTERVAL),
        )
        self.client = client
        self._round = 0
        self._detail_cache = {}
        self._report_due = {}
        self._report_errors = 0

    async def _optional(self, path, params=None):
        try:
            result = await self.client.get(path, params)
            if result is None:
                self._report_errors += 1
            return result
        except (IC2AuthError, IC2RateLimitError):
            raise
        except IC2Error as exc:
            self._report_errors += 1
            _LOGGER.debug("Optional InControl endpoint %s unavailable: %s", path.rsplit("/", 1)[-1], exc)
            return None

    async def _async_update_data(self):
        try:
            raw_orgs = await self.client.get("/rest/o")
            if not isinstance(raw_orgs, (list, dict)):
                raise IC2Error("Inventory pending or invalid")
            orgs = _as_list(raw_orgs)
            devices = {}
            self._round += 1

            for org in orgs:
                oid = org["id"]
                raw_groups = await self.client.get(f"/rest/o/{oid}/g")
                if not isinstance(raw_groups, (list, dict)):
                    raise IC2Error("Group inventory pending or invalid")
                groups = _as_list(raw_groups)
                for group in groups:
                    gid = group.get("id")
                    if gid is None:
                        continue
                    base = f"/rest/o/{oid}/g/{gid}"
                    items = await self._optional(base + "/d", {"has_status": "true"})
                    if not isinstance(items, list):
                        items = await self.client.get(base + "/d")
                    if not isinstance(items, (list, dict)):
                        raise IC2Error("Device inventory pending or invalid")
                    for device in _as_list(items):
                        if not isinstance(device, dict) or device.get("id") is None:
                            continue
                        did = device["id"]
                        key = f"{oid}_{gid}_{did}"
                        path = f"{base}/d/{did}"
                        details = dict(self._detail_cache.get(key, {}))
                        self._report_errors = 0

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

                        # Defer expensive reports until after setup; schedule each device by elapsed time.
                        if self._round > 1 and monotonic() >= self._report_due.get(key, 0):
                            now = datetime.now(_timezone(device))
                            today = now.strftime("%Y-%m-%d")
                            now_str = now.strftime("%Y-%m-%dT%H:%M:%S")
                            past_week = (now - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")
                            past_week_day = (now - timedelta(days=7)).strftime("%Y-%m-%d")

                            calls = {
                                "bandwidth_daily": ("/bandwidth", {"type": "daily"}),
                                "bandwidth_monthly": ("/bandwidth", {"type": "monthly"}),
                                "events": ("/event_log", None),
                                "availability": ("/availability", {"start": past_week, "end": now_str}),
                                "tower_dates": ("/cellular_tower_scan/results/dates", None),
                                "wan_quality_dates": ("/wan_quality/dates", None),
                                "wan_history": (
                                    "/wan_history",
                                    {"start": past_week_day, "end": today, "page": 1, "limit": 100},
                                ),
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
                                    v.get("id")
                                    for v in _as_list(history_metadata.get("wans"))
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
                                result = await self._optional(
                                    path + "/wan_history",
                                    {
                                        "wan_id": numeric_id,
                                        "start": past_week_day,
                                        "end": today,
                                        "page": 1,
                                        "limit": 100,
                                    },
                                )
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
                                    survey = latest_survey(result)
                                    details["tower_scans"] = {"id": [survey] if survey else []}

                            elif details.get("tower_dates") == []:
                                details["tower_scans"] = {"id": []}

                            # The quality endpoint first returns the actual WAN list
                            # for the selected report day. Inventory interfaces are NOT
                            # guaranteed to use the same IDs or include every WAN.
                            quality_dates = _as_list(details.get("wan_quality_dates"))
                            days = sorted(
                                [
                                    row["day"]
                                    for row in quality_dates
                                    if isinstance(row, dict) and isinstance(row.get("day"), str)
                                ],
                                reverse=True,
                            )
                            quality_day = days[0] if days else today
                            quality_start = quality_day + "T00:00:00"
                            quality_end = now_str if quality_day == today else quality_day + "T23:59:59"
                            quality_params = {"start": quality_start, "end": quality_end}
                            quality_meta = await self._optional(path + "/wan_quality", quality_params)

                            # Prefer authoritative WAN IDs from the quality report.
                            # Fall back to inventory / bandwidth IDs only if absent.
                            reported_wans = quality_meta.get("wans", []) if isinstance(quality_meta, dict) else []
                            if reported_wans:
                                candidates = [
                                    (wan.get("id"), wan.get("name")) for wan in reported_wans if isinstance(wan, dict)
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
                                result = await self._optional(
                                    path + "/wan_quality",
                                    {
                                        **quality_params,
                                        "wan_id": wid,
                                    },
                                )
                                if not isinstance(result, dict) or not isinstance(result.get("stat"), list):
                                    continue
                                unique_samples = retain_samples(result["stat"])
                                interface = next(
                                    (
                                        i
                                        for i in _as_list(device.get("interfaces"))
                                        if isinstance(i, dict) and str(i.get("id")) == str(wid)
                                    ),
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
                                details.pop("wan_quality", None)
                                details.pop("wan_quality_wan_name", None)
                                available = [data for data in quality_by_wan.values() if data["stat"]]
                                if available:
                                    newest = max(
                                        available,
                                        key=lambda data: max(
                                            (sample_key(row) for row in data["stat"]),
                                            default=(0, ""),
                                        ),
                                    )
                                    details["wan_quality"] = {"stat": newest["stat"]}
                                    details["wan_quality_wan_name"] = newest["name"]

                            details["report_last_requested"] = datetime.now(timezone.utc).isoformat()
                            details["report_status"] = "partial" if self._report_errors else "complete"
                            self._report_due[key] = monotonic() + (120 if self._report_errors else 1200)
                        self._detail_cache[key] = details
                        devices[key] = {
                            "device": device,
                            "detail": details,
                            "organization": oid,
                            "group": gid,
                            "org_name": org.get("name"),
                        }
            self._detail_cache = {key: self._detail_cache[key] for key in devices}
            self._report_due = {key: due for key, due in self._report_due.items() if key in devices}
            return devices
        except IC2AuthError as exc:
            raise ConfigEntryAuthFailed("Peplink credentials rejected") from exc
        except (IC2Error, KeyError, TypeError, ValueError) as exc:
            raise UpdateFailed("Cannot update Peplink device inventory") from exc
