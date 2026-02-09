import aiohttp

class SolplanetApi:
    def __init__(self, token: str, session: aiohttp.ClientSession):
        self._token = token
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
            "Cookie": f"apitoken={self._token}",
            "User-Agent": "HomeAssistant-Solplanet/1.0",
            "Referer": f"https://internation-cloud.solplanet.net/home/device?plantId={plant_id}",
            "localE": "pt_BR",
        }

        async with self._session.get(url, headers=headers) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            text = await resp.text()

            # Se vier XML/HTML (token inválido/expirado), levanta erro com trecho do corpo
            if "application/json" not in ctype:
                raise Exception(
                    f"Solplanet API returned non-JSON ({resp.status}, {ctype}). "
                    f"Body: {text[:200]}"
                )

            return await resp.json()
