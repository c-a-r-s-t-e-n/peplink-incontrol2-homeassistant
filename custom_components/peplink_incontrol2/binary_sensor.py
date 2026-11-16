from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import PeplinkEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    known = set()

    def discover():
        new = set(c.data or {}) - known
        known.update(new)
        async_add_entities([PeplinkOnline(c, key) for key in new])

    discover()
    entry.async_on_unload(c.async_add_listener(discover))


class PeplinkOnline(PeplinkEntity, BinarySensorEntity):
    _attr_name = "Cloud online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self._attr_unique_id = key + "_online"

    @property
    def is_on(self):
        status = str(self.device_data.get("status", "")).lower()
        return {"online": True, "offline": False}.get(status)
