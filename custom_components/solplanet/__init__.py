from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components import persistent_notification
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
    NOTIFICATION_ID_PREFIX,
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
    notification_id = f"{NOTIFICATION_ID_PREFIX}{entry.entry_id}"

    runtime_status: dict[str, str] = {"status": STATUS_OK}
    cached_data: dict | None = None

    def _set_status(status: str) -> None:
        previous = runtime_status.get("status")
        runtime_status["status"] = status

        if status == STATUS_AUTH_EXPIRED and previous != STATUS_AUTH_EXPIRED:
            persistent_notification.async_create(
                hass,
                (
                    "A autenticação Solplanet expirou.\n\n"
                    "Devido ao captcha de quebra-cabeça do portal, renove manualmente "
                    "os campos token/apitoken na integração para restabelecer a coleta."
                ),
                title="Solplanet: autenticação expirada",
                notification_id=notification_id,
            )
        elif status == STATUS_OK and previous == STATUS_AUTH_EXPIRED:
            persistent_notification.async_dismiss(hass, notification_id)

    async def _async_update_data() -> dict:
        nonlocal cached_data
        try:
            data = await api.fetch_inverter(plant_id)
            _set_status(STATUS_OK)
            cached_data = data
            return data
        except SolplanetAuthError as err:
            refreshed = await api.try_refresh_auth_from_session(plant_id)
            if refreshed:
                _LOGGER.info("Solplanet token refreshed from existing session.")
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_TOKEN: api.token,
                        CONF_APITOKEN: api.apitoken,
                    },
                )
                try:
                    data = await api.fetch_inverter(plant_id)
                    _set_status(STATUS_OK)
                    cached_data = data
                    return data
                except (SolplanetAuthError, SolplanetApiError):
                    pass

            _set_status(STATUS_AUTH_EXPIRED)
            if cached_data is not None:
                _LOGGER.warning("Solplanet authentication failed. Keeping last successful values.")
                return cached_data
            raise UpdateFailed(str(err)) from err
        except SolplanetApiError as err:
            _set_status(STATUS_CONNECTION_ERROR)
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
        persistent_notification.async_dismiss(hass, f"{NOTIFICATION_ID_PREFIX}{entry.entry_id}")
    return unload_ok
