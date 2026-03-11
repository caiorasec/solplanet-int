from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any

import aiohttp


class SolplanetApiError(RuntimeError):
    """Base Solplanet API error."""


class SolplanetAuthError(SolplanetApiError):
    """Raised when authentication is invalid or expired."""


class SolplanetTargetUnavailableError(SolplanetApiError):
    """Raised when the Balena proxy cannot find the inverter on the local network."""

    def __init__(
        self,
        message: str,
        *,
        discovery_subnet: str | None = None,
        discovery_port: str | None = None,
        last_known_ip: str | None = None,
    ) -> None:
        super().__init__(message)
        self.discovery_subnet = discovery_subnet
        self.discovery_port = discovery_port
        self.last_known_ip = last_known_ip


class SolplanetApi:
    def __init__(
        self,
        token: str,
        apitoken: str,
        session: aiohttp.ClientSession,
        base_url: str = "https://internation-cloud.solplanet.net",
        use_local_api: bool = False,
        inverter_sn: str | None = None,
        inverter_index: int = 1,
        local_basic_user: str | None = None,
        local_basic_password: str | None = None,
    ):
        self._token = token
        self._apitoken = apitoken
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._use_local_api = use_local_api
        self._inverter_sn = (inverter_sn or "").strip() or None
        self._inverter_index = max(1, inverter_index)
        user = (local_basic_user or "").strip()
        self._local_basic_auth = (
            aiohttp.BasicAuth(user, local_basic_password or "") if user else None
        )

    @property
    def token(self) -> str:
        return self._token

    @property
    def apitoken(self) -> str:
        return self._apitoken

    async def fetch_inverter(self, plant_id: str) -> dict[str, Any]:
        if self._use_local_api:
            return await self._fetch_inverter_local()

        return await self._fetch_inverter_remote(plant_id)

    async def _fetch_inverter_remote(self, plant_id: str) -> dict[str, Any]:
        """Fetch plant data using plantList and normalize it to sensor expected keys.

        We prefer `/api/plant/plantList` because it's stable in current Solplanet webapp
        and returns the fields required by this integration (power / etoday / etotal).
        """
        url = self._url("/api/plant/plantList?current=1&pageSize=100")

        try:
            async with self._session.get(url, headers=self._headers(plant_id)) as resp:
                payload = await self._parse_json_response(resp)
        except aiohttp.ClientError as err:
            raise SolplanetApiError(f"Solplanet request failed: {err}") from err

        records = payload.get("result")
        if not isinstance(records, list) or not records:
            raise SolplanetApiError(f"Solplanet plantList missing result records: {payload}")

        target = _pick_plant_record(records, plant_id)
        if target is None:
            raise SolplanetApiError(f"Plant {plant_id} not found in plantList response")

        pac_kw = _to_float(target.get("power"))
        e_today = _to_float(target.get("etoday"))
        e_total = _normalize_total_energy(target)

        # Keep compatibility with existing sensor parser (invList-like shape).
        return {
            "code": 200,
            "result": {
                "records": [
                    {
                        "invList": [
                            {
                                "pac": pac_kw,
                                "e_today": e_today,
                                "etotal": e_total,
                            }
                        ]
                    }
                ]
            },
        }

    async def _fetch_inverter_local(self) -> dict[str, Any]:
        try:
            payload = await self._simple_get_json("/getdev.cgi?device=2")
        except aiohttp.ClientError as err:
            raise SolplanetApiError(f"Solplanet local request failed: {err}") from err

        inv_list = payload.get("inv")
        if not isinstance(inv_list, list) or not inv_list:
            raise SolplanetApiError(f"Solplanet local API missing inverter list: {payload}")

        target = _pick_local_inverter(inv_list, self._inverter_sn, self._inverter_index)
        if target is None:
            raise SolplanetApiError("No inverter found for configured SN/index in local API")

        sn_value = target.get("isn")
        if isinstance(sn_value, str) and sn_value.strip():
            self._inverter_sn = sn_value.strip()

        sn = self._inverter_sn
        if not sn:
            raise SolplanetApiError("No inverter SN found in local API")

        try:
            data = await self._simple_get_json(f"/getdevdata.cgi?device=2&sn={sn}")
        except aiohttp.ClientError as err:
            raise SolplanetApiError(f"Solplanet local data request failed: {err}") from err

        # getdevdata.cgi?device=2: pac in W, etd/eto in 0.1kWh.
        pac_kw = _to_float(data.get("pac")) / 1000.0
        e_today = _to_float(data.get("etd")) / 10.0
        e_total = _to_float(data.get("eto")) / 10.0

        return {
            "code": 200,
            "result": {
                "records": [
                    {
                        "invList": [
                            {
                                "pac": pac_kw,
                                "e_today": e_today,
                                "etotal": e_total,
                                "fac": _to_float(data.get("fac")) / 100.0,
                                "vac_1": _to_float(_list_value(data.get("vac"), 0)) / 10.0,
                                "iac_1": _to_float(_list_value(data.get("iac"), 0)) / 100.0,
                                "tmp": _to_float(data.get("tmp")) / 10.0,
                                "pf": _to_float(data.get("pf")) / 100.0,
                                "vpv_1": _to_float(_list_value(data.get("vpv"), 0)) / 10.0,
                                "vpv_2": _to_float(_list_value(data.get("vpv"), 1)) / 10.0,
                                "vpv_3": _to_float(_list_value(data.get("vpv"), 2)) / 10.0,
                                "ipv_1": _to_float(_list_value(data.get("ipv"), 0)) / 100.0,
                                "ipv_2": _to_float(_list_value(data.get("ipv"), 1)) / 100.0,
                                "ipv_3": _to_float(_list_value(data.get("ipv"), 2)) / 100.0,
                                "flg": _to_float(data.get("flg")),
                                "wan": _to_float(data.get("wan")),
                                "err": _to_float(data.get("err")),
                                "sn": sn,
                                "model": str(target.get("model") or ""),
                            }
                        ]
                    }
                ]
            },
        }

    async def try_refresh_auth_from_session(self, plant_id: str) -> bool:
        """Best-effort auth renewal using existing session/cookies, without captcha."""
        if self._use_local_api:
            return False

        endpoints = (
            ("GET", "/api/user/getUserInfo"),
            ("GET", "/api/userManage/getUserInfo"),
            ("POST", "/api/user/refreshToken"),
            ("POST", "/api/userManage/refreshToken"),
        )

        for method, path in endpoints:
            url = self._url(path)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Cookie": f"apitoken={self._apitoken}",
                "Referer": self._referer(plant_id),
                "localE": "pt_BR",
                "User-Agent": "HomeAssistant-Solplanet/1.0",
            }
            if self._token:
                headers["token"] = self._token

            try:
                if method == "GET":
                    resp_ctx = self._session.get(url, headers=headers)
                else:
                    resp_ctx = self._session.post(url, headers=headers, json={})

                async with resp_ctx as resp:
                    if resp.status != 200:
                        continue

                    data = await _safe_json(resp)
                    token = _extract_token(data)
                    apitoken = _extract_apitoken(data)
                    if not token:
                        token = _extract_token_from_headers(resp)
                    if not apitoken:
                        apitoken = _extract_apitoken_from_cookies(resp)

                    if token and apitoken:
                        self._token = token
                        self._apitoken = apitoken
                        return True
            except aiohttp.ClientError:
                continue

        return False

    def _headers(self, plant_id: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "token": self._token,
            "Cookie": f"apitoken={self._apitoken}",
            "Referer": self._referer(plant_id),
            "localE": "pt_BR",
            "User-Agent": "HomeAssistant-Solplanet/1.0",
        }

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _referer(self, plant_id: str) -> str:
        return self._url(f"/home/device?plantId={plant_id}")

    async def _simple_get_json(self, path: str) -> dict[str, Any]:
        async with self._session.get(
            self._url(path),
            auth=self._local_basic_auth if self._use_local_api else None,
        ) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise SolplanetApiError(f"Solplanet HTTP {resp.status}: {text[:250]}")
            try:
                data = await resp.json(content_type=None)
            except Exception as err:
                raise SolplanetApiError(f"Solplanet invalid JSON: {text[:250]}") from err
            if not isinstance(data, dict):
                raise SolplanetApiError("Solplanet response is not a JSON object")
            if data.get("status") == "unavailable":
                raise SolplanetTargetUnavailableError(
                    str(data.get("message") or "Solplanet target not found"),
                    discovery_subnet=_optional_str(data.get("discovery_subnet")),
                    discovery_port=_optional_str(data.get("discovery_port")),
                    last_known_ip=_optional_str(data.get("last_known_ip")),
                )
            return data

    async def _parse_json_response(self, resp: aiohttp.ClientResponse) -> dict[str, Any]:
        ctype = (resp.headers.get("Content-Type") or "").lower()
        text = await resp.text()

        if resp.status in (401, 403):
            raise SolplanetAuthError(f"Solplanet HTTP {resp.status}: authentication failed")

        if resp.status != 200:
            raise SolplanetApiError(f"Solplanet HTTP {resp.status}: {text[:250]}")

        if "application/json" not in ctype:
            raise SolplanetApiError(f"Solplanet non-JSON ({resp.status}, {ctype}). Body: {text[:250]}")

        data = await resp.json()
        code = data.get("code")
        if code in (401, 403):
            raise SolplanetAuthError(f"Solplanet API code {code}: authentication failed")
        if code != 200:
            raise SolplanetApiError(f"Solplanet API code {code}: {data}")

        return data


async def _safe_json(resp: aiohttp.ClientResponse) -> dict[str, Any]:
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "application/json" not in ctype:
        return {}
    try:
        data = await resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _pick_plant_record(records: list[dict[str, Any]], plant_id: str) -> dict[str, Any] | None:
    for row in records:
        if str(row.get("stationid")) == str(plant_id):
            return row
    return records[0] if records else None


def _normalize_total_energy(row: dict[str, Any]) -> float:
    value = _to_float(row.get("etotal"))
    unit = str(row.get("etotalUnit") or "kWh").lower()
    if unit == "mwh":
        return value * 1000
    return value


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _list_value(value: Any, index: int) -> Any:
    if isinstance(value, list) and len(value) > index:
        return value[index]
    return None


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_token(data: dict[str, Any]) -> str | None:
    for path in (
        ("result", "token"),
        ("result", "accessToken"),
        ("data", "token"),
        ("data", "accessToken"),
        ("token",),
        ("accessToken",),
    ):
        value = _deep_get(data, path)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_apitoken(data: dict[str, Any]) -> str | None:
    for path in (
        ("result", "apitoken"),
        ("data", "apitoken"),
        ("apitoken",),
    ):
        value = _deep_get(data, path)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_token_from_headers(resp: aiohttp.ClientResponse) -> str | None:
    for header in ("token", "authorization", "x-auth-token"):
        value = resp.headers.get(header)
        if not value:
            continue
        if header == "authorization" and value.lower().startswith("bearer "):
            value = value[7:]
        value = value.strip()
        if value:
            return value
    return None


def _extract_apitoken_from_cookies(resp: aiohttp.ClientResponse) -> str | None:
    set_cookie_headers = resp.headers.getall("Set-Cookie", [])
    for header in set_cookie_headers:
        cookie = SimpleCookie()
        try:
            cookie.load(header)
        except Exception:
            continue
        morsel = cookie.get("apitoken")
        if morsel and morsel.value:
            return morsel.value
    return None


def _deep_get(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _pick_local_inverter(
    inv_list: list[dict[str, Any]],
    inverter_sn: str | None,
    inverter_index: int,
) -> dict[str, Any] | None:
    if inverter_sn:
        for item in inv_list:
            if str(item.get("isn", "")).strip() == inverter_sn:
                return item

    if not inv_list:
        return None

    index = min(len(inv_list), max(1, inverter_index)) - 1
    return inv_list[index]
