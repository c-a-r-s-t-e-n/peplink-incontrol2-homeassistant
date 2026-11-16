"""Home Assistant UI setup flow."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import IC2AuthError, IC2Client, IC2Error
from .const import DOMAIN


class PeplinkFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            user_input = {key: value.strip() for key, value in user_input.items()}
            client = IC2Client(async_get_clientsession(self.hass), user_input["client_id"], user_input["client_secret"])
            try:
                orgs = await client.get("/rest/o")
                if not isinstance(orgs, list) or not orgs:
                    errors["base"] = "no_organizations"
                else:
                    await self.async_set_unique_id(user_input["client_id"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Peplink InControl 2", data=user_input)
            except IC2AuthError:
                errors["base"] = "invalid_auth"
            except IC2Error:
                errors["base"] = "cannot_connect"
        schema = vol.Schema(
            {
                vol.Required("client_id"): str,
                vol.Required("client_secret"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"cloud_url": "https://incontrol2.peplink.com/"},
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            secret = user_input["client_secret"].strip()
            client = IC2Client(async_get_clientsession(self.hass), entry.data["client_id"], secret)
            try:
                orgs = await client.get("/rest/o")
                if not isinstance(orgs, list) or not orgs:
                    errors["base"] = "no_organizations"
                else:
                    return self.async_update_reload_and_abort(entry, data_updates={"client_secret": secret})
            except IC2AuthError:
                errors["base"] = "invalid_auth"
            except IC2Error:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required("client_secret"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
            ),
            errors=errors,
        )
