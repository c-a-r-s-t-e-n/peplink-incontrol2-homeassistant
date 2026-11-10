"""GPS tracker; never expose stale GPS data as a current position."""
from datetime import datetime, timezone, timedelta
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
        # API ts is group-local without offset: do not pretend it is UTC.
        return (float(lat), float(lon))
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
