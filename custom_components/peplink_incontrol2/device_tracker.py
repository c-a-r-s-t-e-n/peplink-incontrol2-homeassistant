"""Current and last-known Peplink GPS trackers with explicit freshness."""
from homeassistant.components.device_tracker import TrackerEntity, SourceType
from .const import DOMAIN
from .entity import PeplinkEntity
from .gps import location_info


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for key in coordinator.data:
        entities.extend([PeplinkTracker(coordinator, key), PeplinkLastKnownTracker(coordinator, key)])
    async_add_entities(entities)


class _BasePeplinkTracker(PeplinkEntity, TrackerEntity):
    """Shared GPS data and stable metadata for both trackers."""

    @property
    def source_type(self):
        return SourceType.GPS

    def _point(self):
        return location_info(
            self.detail.get("location"),
            self.device_data.get("group_timezone_label") or "UTC",
            online=str(self.device_data.get("status", "")).lower() == "online",
        )

    @property
    def latitude(self):
        point = self._point()
        if point and (self._historical or point["is_current"]):
            return point["latitude"]
        return None

    @property
    def longitude(self):
        point = self._point()
        if point and (self._historical or point["is_current"]):
            return point["longitude"]
        return None

    @property
    def extra_state_attributes(self):
        point = self._point()
        if point is None:
            return {"position_type": "historical" if self._historical else "current"}
        return {
            "position_type": "historical" if self._historical else "current",
            "last_reported_utc": point["measured_at"],
            "gps_age_minutes": point["age_minutes"],
            "position_is_current": point["is_current"],
            "router_cloud_online": str(self.device_data.get("status", "")).lower() == "online",
            "historical_position_warning": (
                "Last reported position, not live tracking" if self._historical else None
            ),
        }


class PeplinkTracker(_BasePeplinkTracker):
    """Original stable entity: never exposes outdated position as current."""

    _attr_name = "GPS location"
    _historical = False

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self._attr_unique_id = key + "_gps"


class PeplinkLastKnownTracker(_BasePeplinkTracker):
    """Separate explicitly historical map pin, never used for live position alerts."""

    _attr_name = "Last known GPS (historical)"
    _historical = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self._attr_unique_id = key + "_gps_last_known"
