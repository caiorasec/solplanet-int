from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolplanetApi, SolplanetApiError, SolplanetAuthError
from .const import CONF_APITOKEN, CONF_PLANT_ID, CONF_TOKEN, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLANT_ID): str,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_APITOKEN): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = SolplanetApi(
                token=user_input[CONF_TOKEN],
                apitoken=user_input[CONF_APITOKEN],
                session=session,
            )

            try:
                await api.fetch_inverter(user_input[CONF_PLANT_ID])
                await self.async_set_unique_id(user_input[CONF_PLANT_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Solplanet", data=user_input)
            except SolplanetAuthError:
                errors["base"] = "invalid_auth"
            except SolplanetApiError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)
