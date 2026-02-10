from __future__ import annotations

import aiohttp


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

        async with self._session.get(url, headers=headers) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            text = await resp.text()

            if resp.status != 200:
                raise RuntimeError(f"Solplanet HTTP {resp.status}: {text[:250]}")

            if "application/json" not in ctype:
                raise RuntimeError(
                    f"Solplanet non-JSON ({resp.status}, {ctype}). Body: {text[:250]}"
                )

            return await resp.json()
