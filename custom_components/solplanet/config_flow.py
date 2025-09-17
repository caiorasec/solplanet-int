import voluptuous as vol
from homeassistant import config_entries
import aiohttp
from .const import DOMAIN
from .api import SolplanetApi

DATA_SCHEMA = vol.Schema({
    vol.Required("username"): str,
    vol.Required("password"): str,
    vol.Required("plant_id"): str,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            session = aiohttp.ClientSession()
            api = SolplanetApi(user_input["username"], user_input["password"], session)
            try:
                await api.login()
            except Exception:
                return self.async_abort(reason="auth_failed")

            return self.async_create_entry(
                title="Solplanet",
                data=user_input,
            )
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
