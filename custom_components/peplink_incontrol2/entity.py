"""Shared entity metadata."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class PeplinkEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key

    @property
    def available(self):
        return super().available and self.key in (self.coordinator.data or {})

    @property
    def item(self):
        return (self.coordinator.data or {}).get(self.key, {})

    @property
    def device_data(self):
        return self.item.get("device", {})

    @property
    def detail(self):
        return self.item.get("detail", {})

    @property
    def device_info(self):
        d = self.device_data
        return DeviceInfo(
            identifiers={(DOMAIN, self.key)},
            name=d.get("name", self.key),
            configuration_url="https://incontrol2.peplink.com/",
            manufacturer="Peplink",
            model=d.get("product_name") or d.get("model"),
            sw_version=d.get("fw_ver"),
            serial_number=d.get("sn"),
        )
