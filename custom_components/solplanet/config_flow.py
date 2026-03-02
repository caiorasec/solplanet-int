from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolplanetApi, SolplanetApiError, SolplanetAuthError
from .const import (
    CONF_APITOKEN,
    CONF_CONNECTION_MODE,
    CONF_INVERTER_INDEX,
    CONF_INVERTER_SN,
    CONF_LOCAL_BASIC_PASSWORD,
    CONF_LOCAL_BASIC_USER,
    CONF_LOCAL_HOST,
    CONF_LOCAL_PORT,
    CONF_LOCAL_USE_HTTPS,
    CONF_PLANT_ID,
    CONF_TOKEN,
    CONNECTION_MODE_LOCAL,
    CONNECTION_MODE_REMOTE,
    DEFAULT_INVERTER_INDEX,
    DEFAULT_LOCAL_PORT,
    DEFAULT_REMOTE_BASE_URL,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLANT_ID): str,
        vol.Optional(CONF_CONNECTION_MODE, default=CONNECTION_MODE_REMOTE): vol.In(
            [CONNECTION_MODE_REMOTE, CONNECTION_MODE_LOCAL]
        ),
    }
)

STEP_REMOTE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_APITOKEN): str,
    }
)

STEP_LOCAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCAL_HOST): str,
        vol.Optional(CONF_LOCAL_PORT, default=DEFAULT_LOCAL_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_LOCAL_USE_HTTPS, default=False): bool,
        vol.Optional(CONF_LOCAL_BASIC_USER, default=""): str,
        vol.Optional(CONF_LOCAL_BASIC_PASSWORD, default=""): str,
        vol.Optional(CONF_INVERTER_SN, default=""): str,
        vol.Optional(CONF_INVERTER_INDEX, default=DEFAULT_INVERTER_INDEX): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=4)
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._base_data: dict[str, Any] = {}

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors={})

        self._base_data = {
            CONF_PLANT_ID: user_input[CONF_PLANT_ID],
            CONF_CONNECTION_MODE: user_input.get(CONF_CONNECTION_MODE, CONNECTION_MODE_REMOTE),
        }

        if self._base_data[CONF_CONNECTION_MODE] == CONNECTION_MODE_LOCAL:
            return await self.async_step_local()
        return await self.async_step_remote()

    async def async_step_remote(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                **self._base_data,
                CONF_TOKEN: user_input[CONF_TOKEN],
                CONF_APITOKEN: user_input[CONF_APITOKEN],
                CONF_LOCAL_HOST: "",
                CONF_LOCAL_PORT: DEFAULT_LOCAL_PORT,
                CONF_LOCAL_USE_HTTPS: False,
                CONF_LOCAL_BASIC_USER: "",
                CONF_LOCAL_BASIC_PASSWORD: "",
                CONF_INVERTER_SN: "",
                CONF_INVERTER_INDEX: DEFAULT_INVERTER_INDEX,
            }
            error = await _async_validate_connection(self.hass, data)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(data[CONF_PLANT_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Solplanet", data=data)

        return self.async_show_form(step_id="remote", data_schema=STEP_REMOTE_SCHEMA, errors=errors)

    async def async_step_local(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                **self._base_data,
                CONF_TOKEN: "",
                CONF_APITOKEN: "",
                CONF_LOCAL_HOST: user_input[CONF_LOCAL_HOST],
                CONF_LOCAL_PORT: user_input[CONF_LOCAL_PORT],
                CONF_LOCAL_USE_HTTPS: user_input[CONF_LOCAL_USE_HTTPS],
                CONF_LOCAL_BASIC_USER: user_input[CONF_LOCAL_BASIC_USER],
                CONF_LOCAL_BASIC_PASSWORD: user_input[CONF_LOCAL_BASIC_PASSWORD],
                CONF_INVERTER_SN: user_input[CONF_INVERTER_SN],
                CONF_INVERTER_INDEX: user_input[CONF_INVERTER_INDEX],
            }
            error = await _async_validate_connection(self.hass, data)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(data[CONF_PLANT_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Solplanet", data=data)

        return self.async_show_form(step_id="local", data_schema=STEP_LOCAL_SCHEMA, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return SolplanetOptionsFlow(config_entry)


class SolplanetOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._entry = config_entry
        self._selected_mode = self._entry_value(CONF_CONNECTION_MODE, CONNECTION_MODE_REMOTE)

    async def async_step_init(self, user_input=None):
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_CONNECTION_MODE,
                        default=self._selected_mode,
                    ): vol.In([CONNECTION_MODE_REMOTE, CONNECTION_MODE_LOCAL])
                }
            )
            return self.async_show_form(step_id="init", data_schema=schema, errors={})

        self._selected_mode = user_input[CONF_CONNECTION_MODE]
        if self._selected_mode == CONNECTION_MODE_LOCAL:
            return await self.async_step_local()
        return await self.async_step_remote()

    async def async_step_remote(self, user_input=None):
        errors: dict[str, str] = {}
        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN, default=self._entry.data.get(CONF_TOKEN, "")): str,
                vol.Required(CONF_APITOKEN, default=self._entry.data.get(CONF_APITOKEN, "")): str,
            }
        )

        if user_input is not None:
            data = {
                **self._entry.data,
                CONF_CONNECTION_MODE: CONNECTION_MODE_REMOTE,
                CONF_TOKEN: user_input[CONF_TOKEN],
                CONF_APITOKEN: user_input[CONF_APITOKEN],
            }
            error = await _async_validate_connection(self.hass, data)
            if error:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={
                        **self._entry.data,
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_APITOKEN: user_input[CONF_APITOKEN],
                    },
                )
                return self.async_create_entry(
                    title="",
                    data={CONF_CONNECTION_MODE: CONNECTION_MODE_REMOTE},
                )

        return self.async_show_form(step_id="remote", data_schema=schema, errors=errors)

    async def async_step_local(self, user_input=None):
        errors: dict[str, str] = {}
        schema = vol.Schema(
            {
                vol.Required(CONF_LOCAL_HOST, default=self._entry_value(CONF_LOCAL_HOST, "")): str,
                vol.Optional(
                    CONF_LOCAL_PORT,
                    default=self._entry_value(CONF_LOCAL_PORT, DEFAULT_LOCAL_PORT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Optional(
                    CONF_LOCAL_USE_HTTPS,
                    default=self._entry_value(CONF_LOCAL_USE_HTTPS, False),
                ): bool,
                vol.Optional(
                    CONF_LOCAL_BASIC_USER,
                    default=self._entry_value(CONF_LOCAL_BASIC_USER, ""),
                ): str,
                vol.Optional(
                    CONF_LOCAL_BASIC_PASSWORD,
                    default=self._entry_value(CONF_LOCAL_BASIC_PASSWORD, ""),
                ): str,
                vol.Optional(
                    CONF_INVERTER_SN,
                    default=self._entry_value(CONF_INVERTER_SN, ""),
                ): str,
                vol.Optional(
                    CONF_INVERTER_INDEX,
                    default=self._entry_value(CONF_INVERTER_INDEX, DEFAULT_INVERTER_INDEX),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
            }
        )

        if user_input is not None:
            data = {
                **self._entry.data,
                CONF_CONNECTION_MODE: CONNECTION_MODE_LOCAL,
                CONF_LOCAL_HOST: user_input[CONF_LOCAL_HOST],
                CONF_LOCAL_PORT: user_input[CONF_LOCAL_PORT],
                CONF_LOCAL_USE_HTTPS: user_input[CONF_LOCAL_USE_HTTPS],
                CONF_LOCAL_BASIC_USER: user_input[CONF_LOCAL_BASIC_USER],
                CONF_LOCAL_BASIC_PASSWORD: user_input[CONF_LOCAL_BASIC_PASSWORD],
                CONF_INVERTER_SN: user_input[CONF_INVERTER_SN],
                CONF_INVERTER_INDEX: user_input[CONF_INVERTER_INDEX],
            }
            error = await _async_validate_connection(self.hass, data)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_CONNECTION_MODE: CONNECTION_MODE_LOCAL,
                        CONF_LOCAL_HOST: user_input[CONF_LOCAL_HOST],
                        CONF_LOCAL_PORT: user_input[CONF_LOCAL_PORT],
                        CONF_LOCAL_USE_HTTPS: user_input[CONF_LOCAL_USE_HTTPS],
                        CONF_LOCAL_BASIC_USER: user_input[CONF_LOCAL_BASIC_USER],
                        CONF_LOCAL_BASIC_PASSWORD: user_input[CONF_LOCAL_BASIC_PASSWORD],
                        CONF_INVERTER_SN: user_input[CONF_INVERTER_SN],
                        CONF_INVERTER_INDEX: user_input[CONF_INVERTER_INDEX],
                    },
                )

        return self.async_show_form(step_id="local", data_schema=schema, errors=errors)

    def _entry_value(self, key: str, default: Any) -> Any:
        return self._entry.options.get(key, self._entry.data.get(key, default))


def _resolve_base_url(user_input: dict) -> str | None:
    mode = user_input.get(CONF_CONNECTION_MODE, CONNECTION_MODE_REMOTE)
    if mode != CONNECTION_MODE_LOCAL:
        return DEFAULT_REMOTE_BASE_URL

    host = str(user_input.get(CONF_LOCAL_HOST, "")).strip()
    if not host:
        return None

    if "://" in host:
        parsed = urlsplit(host)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        return None

    port = int(user_input.get(CONF_LOCAL_PORT, DEFAULT_LOCAL_PORT))
    scheme = "https" if user_input.get(CONF_LOCAL_USE_HTTPS, False) else "http"
    return f"{scheme}://{host}:{port}"


async def _async_validate_connection(hass, user_input: dict[str, Any]) -> str | None:
    base_url = _resolve_base_url(user_input)
    if not base_url:
        return "invalid_local_config"

    session = async_get_clientsession(hass)
    api = SolplanetApi(
        token=user_input.get(CONF_TOKEN, ""),
        apitoken=user_input.get(CONF_APITOKEN, ""),
        session=session,
        base_url=base_url,
        use_local_api=user_input.get(CONF_CONNECTION_MODE, CONNECTION_MODE_REMOTE)
        == CONNECTION_MODE_LOCAL,
        inverter_sn=str(user_input.get(CONF_INVERTER_SN, "")).strip() or None,
        inverter_index=int(user_input.get(CONF_INVERTER_INDEX, DEFAULT_INVERTER_INDEX)),
        local_basic_user=str(user_input.get(CONF_LOCAL_BASIC_USER, "")).strip() or None,
        local_basic_password=str(user_input.get(CONF_LOCAL_BASIC_PASSWORD, "")),
    )

    try:
        await api.fetch_inverter(user_input[CONF_PLANT_ID])
        return None
    except SolplanetAuthError:
        return "invalid_auth"
    except SolplanetApiError:
        return "cannot_connect"
