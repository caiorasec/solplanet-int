import aiohttp

class SolplanetApi:
    def __init__(self, token: str, apitoken: str, session: aiohttp.ClientSession):
        self._token = token          # header token (curto)
        self._apitoken = apitoken    # cookie apitoken (JWT)
        self._session = session

    async def fetch_inverter(self, plant_id: str):
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

            if "application/json" not in ctype:
                raise Exception(
                    f"Solplanet non-JSON ({resp.status}, {ctype}). Body: {text[:250]}"
                )

            return await resp.json()
