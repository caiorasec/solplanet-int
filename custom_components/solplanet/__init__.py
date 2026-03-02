from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from urllib.parse import urlsplit

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SolplanetApi, SolplanetApiError, SolplanetAuthError
from .const import (
    CONF_APITOKEN,
    CONF_CONNECTION_MODE,
    CONF_LOCAL_HOST,
    CONF_LOCAL_PORT,
    CONF_LOCAL_USE_HTTPS,
    CONF_LOCAL_BASIC_PASSWORD,
    CONF_LOCAL_BASIC_USER,
    CONF_INVERTER_INDEX,
    CONF_INVERTER_SN,
    CONF_PLANT_ID,
    CONF_TOKEN,
    CONNECTION_MODE_LOCAL,
    CONNECTION_MODE_REMOTE,
    COORDINATOR,
    DEFAULT_INVERTER_INDEX,
    DEFAULT_LOCAL_PORT,
    DEFAULT_REMOTE_BASE_URL,
    DOMAIN,
    NOTIFICATION_ID_PREFIX,
    PLATFORMS,
    RUNTIME_STATUS,
    STATUS_AUTH_EXPIRED,
    STATUS_CONNECTION_ERROR,
    STATUS_OK,
)

_LOGGER = logging.getLogger(__name__)
PROACTIVE_REFRESH_INTERVAL = timedelta(hours=6)



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = SolplanetApi(
        token=entry.data[CONF_TOKEN],
        apitoken=entry.data[CONF_APITOKEN],
        session=session,
        base_url=_entry_base_url(entry),
        use_local_api=_entry_is_local(entry),
        inverter_sn=_entry_value(entry, CONF_INVERTER_SN, ""),
        inverter_index=int(_entry_value(entry, CONF_INVERTER_INDEX, DEFAULT_INVERTER_INDEX)),
        local_basic_user=_entry_value(entry, CONF_LOCAL_BASIC_USER, ""),
        local_basic_password=_entry_value(entry, CONF_LOCAL_BASIC_PASSWORD, ""),
    )
    plant_id = entry.data[CONF_PLANT_ID]
    notification_id = f"{NOTIFICATION_ID_PREFIX}{entry.entry_id}"

    runtime_status: dict[str, str] = {"status": STATUS_OK}
    cached_data: dict | None = None
    last_refresh_attempt: datetime | None = None

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

    async def _persist_refreshed_auth() -> None:
        if (
            api.token == entry.data.get(CONF_TOKEN)
            and api.apitoken == entry.data.get(CONF_APITOKEN)
        ):
            return

        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_TOKEN: api.token,
                CONF_APITOKEN: api.apitoken,
            },
        )

    async def _refresh_auth(reason: str) -> bool:
        nonlocal last_refresh_attempt
        refreshed = await api.try_refresh_auth_from_session(plant_id)
        last_refresh_attempt = datetime.now(timezone.utc)

        if not refreshed:
            return False

        _LOGGER.info("Solplanet token refreshed from existing session (%s).", reason)
        await _persist_refreshed_auth()
        return True

    async def _async_update_data() -> dict:
        nonlocal cached_data
        now = datetime.now(timezone.utc)
        should_do_proactive_refresh = (
            last_refresh_attempt is None
            or now - last_refresh_attempt >= PROACTIVE_REFRESH_INTERVAL
        )
        if should_do_proactive_refresh:
            await _refresh_auth("proactive")

        try:
            data = await api.fetch_inverter(plant_id)
            _set_status(STATUS_OK)
            cached_data = data
            return data
        except SolplanetAuthError as err:
            refreshed = await _refresh_auth("after-auth-error")
            if refreshed:
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


def _entry_base_url(entry: ConfigEntry) -> str:
    mode = _entry_value(entry, CONF_CONNECTION_MODE, CONNECTION_MODE_REMOTE)
    if mode != CONNECTION_MODE_LOCAL:
        return DEFAULT_REMOTE_BASE_URL

    host = str(_entry_value(entry, CONF_LOCAL_HOST, "")).strip()
    if not host:
        return DEFAULT_REMOTE_BASE_URL

    if "://" in host:
        parsed = urlsplit(host)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    port = int(_entry_value(entry, CONF_LOCAL_PORT, DEFAULT_LOCAL_PORT))
    scheme = "https" if _entry_value(entry, CONF_LOCAL_USE_HTTPS, False) else "http"
    return f"{scheme}://{host}:{port}"


def _entry_is_local(entry: ConfigEntry) -> bool:
    return _entry_value(entry, CONF_CONNECTION_MODE, CONNECTION_MODE_REMOTE) == CONNECTION_MODE_LOCAL


def _entry_value(entry: ConfigEntry, key: str, default):
    return entry.options.get(key, entry.data.get(key, default))
