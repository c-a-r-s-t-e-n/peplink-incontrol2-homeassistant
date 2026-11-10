"""Home Assistant UI setup flow."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN
from .api import IC2Client, IC2Error

class PeplinkFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            client = IC2Client(async_get_clientsession(self.hass), user_input["client_id"], user_input["client_secret"])
            try:
                orgs = await client.get("/rest/o")
                if not isinstance(orgs, list) or not orgs:
                    errors["base"] = "no_organizations"
                else:
                    await self.async_set_unique_id(user_input["client_id"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Peplink InControl 2", data=user_input)
            except IC2Error:
                errors["base"] = "cannot_connect"
        schema = vol.Schema({vol.Required("client_id"): str, vol.Required("client_secret"): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
