from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SolplanetApi, SolplanetApiError, SolplanetAuthError
from .const import (
    CONF_APITOKEN,
    CONF_PLANT_ID,
    CONF_TOKEN,
    COORDINATOR,
    DOMAIN,
    PLATFORMS,
    RUNTIME_STATUS,
    STATUS_AUTH_EXPIRED,
    STATUS_CONNECTION_ERROR,
    STATUS_OK,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = SolplanetApi(
        token=entry.data[CONF_TOKEN],
        apitoken=entry.data[CONF_APITOKEN],
        session=session,
    )
    plant_id = entry.data[CONF_PLANT_ID]
    runtime_status: dict[str, str] = {"status": STATUS_OK}
    cached_data: dict | None = None

    async def _async_update_data() -> dict:
        nonlocal cached_data
        try:
            data = await api.fetch_inverter(plant_id)
            runtime_status["status"] = STATUS_OK
            cached_data = data
            return data
        except SolplanetAuthError as err:
            runtime_status["status"] = STATUS_AUTH_EXPIRED
            if cached_data is not None:
                _LOGGER.warning("Solplanet authentication failed. Keeping last successful values.")
                return cached_data
            raise UpdateFailed(str(err)) from err
        except SolplanetApiError as err:
            runtime_status["status"] = STATUS_CONNECTION_ERROR
            if cached_data is not None:
                _LOGGER.warning(
                    "Solplanet update failed (%s). Keeping last successful values.", err
                )
                return cached_data
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        RUNTIME_STATUS: runtime_status,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
