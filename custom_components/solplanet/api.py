from __future__ import annotations

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

    async def fetch_inverter(self, plant_id: str) -> dict:
        url = (
            "https://internation-cloud.solplanet.net/api/plant/invList"
            f"?current=1&pageSize=10&plantId={plant_id}"
        )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "token": self._token,
            "Cookie": f"apitoken={self._apitoken}",
            "Referer": f"https://internation-cloud.solplanet.net/home/device?plantId={plant_id}",
            "localE": "pt_BR",
            "User-Agent": "HomeAssistant-Solplanet/1.0",
        }

        try:
            async with self._session.get(url, headers=headers) as resp:
                ctype = (resp.headers.get("Content-Type") or "").lower()
                text = await resp.text()

                if resp.status in (401, 403):
                    raise SolplanetAuthError(f"Solplanet HTTP {resp.status}: authentication failed")

                if resp.status != 200:
                    raise SolplanetApiError(f"Solplanet HTTP {resp.status}: {text[:250]}")

                if "application/json" not in ctype:
                    raise SolplanetApiError(
                        f"Solplanet non-JSON ({resp.status}, {ctype}). Body: {text[:250]}"
                    )

                data = await resp.json()
                code = data.get("code")
                if code in (401, 403):
                    raise SolplanetAuthError(f"Solplanet API code {code}: authentication failed")
                if code != 200:
                    raise SolplanetApiError(f"Solplanet API code {code}: {data}")

                return data
        except aiohttp.ClientError as err:
            raise SolplanetApiError(f"Solplanet request failed: {err}") from err
