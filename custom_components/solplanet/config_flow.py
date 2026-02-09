import voluptuous as vol
from homeassistant import config_entries
import aiohttp

from .const import DOMAIN
from .api import SolplanetApi

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("plant_id"): str,
        vol.Required("token"): str,
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            session = aiohttp.ClientSession()
            api = SolplanetApi(user_input["token"], session)
            try:
                data = await api.fetch_inverter(user_input["plant_id"])
                # valida estrutura esperada
                if data.get("code") != 200:
                    raise Exception(f"API code != 200: {data}")
            except Exception:
                await session.close()
                return self.async_abort(reason="auth_failed")

            await session.close()
            return self.async_create_entry(
                title="Solplanet",
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
