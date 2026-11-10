"""GPS tracker; never expose stale GPS data as a current position."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from homeassistant.components.device_tracker import TrackerEntity, SourceType
from .const import DOMAIN
from .entity import PeplinkEntity

async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PeplinkTracker(c, k) for k in c.data])

class PeplinkTracker(PeplinkEntity, TrackerEntity):
    _attr_name = "GPS location"
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self._attr_unique_id = key + "_gps"
    @property
    def source_type(self):
        return SourceType.GPS
    @property
    def location(self):
        x = self.detail.get("location")
        if not isinstance(x, dict) or x.get("isStatic") is True:
            return None
        lat, lon = x.get("la"), x.get("lo")
        if lat is None or lon is None:
            return None
        # Prefer GPS timestamp validation; a device offline must not be shown as current.
        if str(self.device_data.get("status", "")).lower() != "online":
            return None
        # InControl timestamps are group-local. Reject old positions even if a
        # previously online router continues to report its last position.
        stamp = x.get("ts")
        if not stamp:
            return None
        try:
            measured = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if measured.tzinfo is None:
                measured = measured.replace(tzinfo=ZoneInfo(
                    self.device_data.get("group_timezone_label") or "UTC"
                ))
            age = datetime.now(timezone.utc) - measured.astimezone(timezone.utc)
            if age < timedelta(minutes=-5) or age > timedelta(minutes=30):
                return None
            return (float(lat), float(lon))
        except (ValueError, TypeError, ZoneInfoNotFoundError, KeyError):
            return None
    @property
    def latitude(self):
        pt = self.location
        return pt[0] if pt else None
    @property
    def longitude(self):
        pt = self.location
        return pt[1] if pt else None
    @property
    def extra_state_attributes(self):
        x = self.detail.get("location")
        if not isinstance(x, dict):
            return {}
        return {"last_reported_at_group_time": x.get("ts"), "static_location": x.get("isStatic"),
                "speed_reported": x.get("sp"), "altitude_reported": x.get("at"),
                "note": "Coordinates may be old; inspect timestamp before using automations"}
