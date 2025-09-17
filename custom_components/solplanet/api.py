import aiohttp

class SolplanetApi:
    def __init__(self, username, password, session: aiohttp.ClientSession):
        self._username = username
        self._password = password
        self._session = session
        self._token = None

    async def login(self):
        """Autentica na Solplanet e guarda o token"""
        url = f"https://internation-cloud.solplanet.net/api/user/login?account={self._username}&password={self._password}"
        async with self._session.post(url) as resp:
            data = await resp.json()
            if "data" not in data or "token" not in data["data"]:
                raise Exception(f"Falha no login: {data}")
            self._token = data["data"]["token"]
        return self._token

    async def fetch_inverter(self, plant_id: str):
        """Busca dados do inversor usando token válido"""
        if not self._token:
            await self.login()

        url = f"https://internation-cloud.solplanet.net/api/plant/invList?current=1&pageSize=10&plantId={plant_id}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "token": self._token,
            "Cookie": f"apitoken={self._token}"
        }
        async with self._session.get(url, headers=headers) as resp:
            return await resp.json()
