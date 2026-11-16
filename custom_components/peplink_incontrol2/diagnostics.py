"""Allowlisted diagnostics without locations, credentials or device identifiers."""

from collections import Counter

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    devices = list((coordinator.data or {}).values())
    return {
        "last_update_success": coordinator.last_update_success,
        "device_count": len(devices),
        "report_coverage": dict(Counter(item.get("detail", {}).get("report_status", "waiting") for item in devices)),
        "quality_wan_count": sum(len(item.get("detail", {}).get("wan_quality_by_wan", {})) for item in devices),
        "poll_interval_seconds": coordinator.update_interval.total_seconds(),
    }
