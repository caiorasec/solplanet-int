from __future__ import annotations

from typing import Any

import aiohttp


class SolplanetApiError(RuntimeError):
    """Base Solplanet API error."""


class SolplanetAuthError(SolplanetApiError):
    """Raised when authentication is invalid or expired."""


class SolplanetApi:
    def __init__(self, token: str, apitoken: str, session: aiohttp.ClientSession):
        self._token = token
        self._apitoken = apitoken
        self._session = session

    @property
    def token(self) -> str:
        return self._token

    @property
    def apitoken(self) -> str:
        return self._apitoken

    async def fetch_inverter(self, plant_id: str) -> dict[str, Any]:
        """Fetch plant data using plantList and normalize it to sensor expected keys.

        We prefer `/api/plant/plantList` because it's stable in current Solplanet webapp
        and returns the fields required by this integration (power / etoday / etotal).
        """
        url = "https://internation-cloud.solplanet.net/api/plant/plantList?current=1&pageSize=100"

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

    async def try_refresh_auth_from_session(self, plant_id: str) -> bool:
        """Best-effort auth renewal using existing session/cookies, without captcha."""
        endpoints = (
            ("GET", "/api/user/getUserInfo"),
            ("GET", "/api/userManage/getUserInfo"),
            ("POST", "/api/user/refreshToken"),
            ("POST", "/api/userManage/refreshToken"),
        )

        for method, path in endpoints:
            url = f"https://internation-cloud.solplanet.net{path}"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Cookie": f"apitoken={self._apitoken}",
                "Referer": f"https://internation-cloud.solplanet.net/home/device?plantId={plant_id}",
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
            "Referer": f"https://internation-cloud.solplanet.net/home/device?plantId={plant_id}",
            "localE": "pt_BR",
            "User-Agent": "HomeAssistant-Solplanet/1.0",
        }

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


def _extract_token(data: dict[str, Any]) -> str | None:
    for path in (
        ("result", "token"),
        ("data", "token"),
        ("token",),
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


def _deep_get(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
