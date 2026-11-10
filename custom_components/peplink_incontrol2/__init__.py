"""Peplink InControl 2 read-only HA integration."""
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN
from .api import IC2Client
from .coordinator import PeplinkCoordinator

PLATFORMS = ["binary_sensor", "sensor", "device_tracker"]

async def async_setup_entry(hass, entry):
    client = IC2Client(async_get_clientsession(hass), entry.data["client_id"], entry.data["client_secret"])
    coordinator = PeplinkCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass, entry):
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return result
