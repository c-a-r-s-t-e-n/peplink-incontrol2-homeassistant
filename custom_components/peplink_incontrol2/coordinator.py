"""Centralized polling and optional diagnostic fetches."""
from datetime import timedelta
import asyncio
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import IC2Error
from .const import DOMAIN, DEFAULT_INTERVAL

_LOGGER = logging.getLogger(__name__)

class PeplinkCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, client):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=DEFAULT_INTERVAL))
        self.client = client
        self._round = 0
        self._detail_cache = {}

    async def _optional(self, path, params=None):
        try:
            return await self.client.get(path, params)
        except IC2Error as exc:
            _LOGGER.debug("Optional Peplink endpoint not available (%s): %s", path.rsplit('/', 1)[-1], exc)
            return None

    async def _async_update_data(self):
        try:
            orgs = await self.client.get("/rest/o") or []
            devices = {}
            self._round += 1
            for org in orgs:
                oid = org["id"]
                groups = await self.client.get(f"/rest/o/{oid}/g") or []
                for group in groups:
                    gid = group.get("id")
                    if gid is None:
                        continue
                    base = f"/rest/o/{oid}/g/{gid}"
                    # has_status includes optional fresh WAN information; PENDING or missing fields are normal
                    items = await self._optional(base + "/d", {"has_status": "true"})
                    if not isinstance(items, list):
                        items = await self.client.get(base + "/d") or []
                    for device in items:
                        did = device.get("id")
                        if did is None:
                            continue
                        key = f"{oid}_{gid}_{did}"
                        path = f"{base}/d/{did}"
                        details = self._detail_cache.get(key, {})
                        # GPS every poll. Slow reports every 10 polls (~20min)
                        location = await self._optional(path + "/loc")
                        if isinstance(location, list) and location:
                            details["location"] = location[0]
                        elif isinstance(location, dict):
                            details["location"] = location
                        if self._round == 1 or self._round % 10 == 0:
                            paths = {
                                "bandwidth_daily": ("/bandwidth", {"type": "daily"}),
                                "bandwidth_monthly": ("/bandwidth", {"type": "monthly"}),
                                "wan_quality": ("/wan_quality", None),
                                "wan_history": ("/wan_history", None),
                                "events": ("/event_log", None),
                                "tower_scans": ("/cellular_tower_scan/results", None),
                                "availability": ("/availability", None),
                            }
                            for name, (suffix, params) in paths.items():
                                output = await self._optional(path + suffix, params)
                                if output is not None:
                                    details[name] = output
                            # /wan_quality returns available WANs first; per-WAN ID yields actual samples.
                            quality = details.get("wan_quality")
                            if isinstance(quality, dict):
                                wans = quality.get("wans")
                                if isinstance(wans, list):
                                    for wan in wans[:4]:
                                        wid = wan.get("id") if isinstance(wan, dict) else None
                                        if isinstance(wid, int) and wid > 0:
                                            samples = await self._optional(path + "/wan_quality", {"wan_id": wid})
                                            if isinstance(samples, dict) and samples.get("stat"):
                                                details["wan_quality"] = samples
                                                details["wan_quality_wan_name"] = wan.get("name")
                                                break
                        self._detail_cache[key] = details
                        devices[key] = {"device": device, "detail": details, "organization": oid,
                                        "group": gid, "org_name": org.get("name")}
            return devices
        except (IC2Error, KeyError, TypeError) as exc:
            raise UpdateFailed("Cannot update Peplink organization/device list") from exc
