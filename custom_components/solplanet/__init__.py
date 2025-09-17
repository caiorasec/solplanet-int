from datetime import timedelta
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, PLATFORMS
from .api import SolplanetApi
import aiohttp

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp.ClientSession()
    api = SolplanetApi(entry.data["username"], entry.data["password"], session)
    await api.login()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "plant_id": entry.data["plant_id"],
    }

    # 🔄 Atualiza o token a cada 4 horas
    async def refresh_token(now):
        try:
            await api.login()
        except Exception as e:
            hass.logger.warning("Falha ao renovar token Solplanet: %s", e)

    async_track_time_interval(hass, refresh_token, timedelta(hours=4))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
