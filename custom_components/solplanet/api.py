import aiohttp

class SolplanetApi:
    def __init__(self, username, password, session: aiohttp.ClientSession):
        self._username = username
        self._password = password
        self._session = session
        self._token = None

    async def login(self):
        url = "https://account.solplanet.net/api/oauth/token"
        payload = {
            "username": self._username,
            "password": self._password,
            "grant_type": "password"
        }
        async with self._session.post(url, data=payload) as resp:
            data = await resp.json()
            self._token = data.get("access_token")
        return self._token

    async def fetch_inverter(self, plant_id: str):
        url = f"https://internation-cloud.solplanet.net/api/plant/invList?current=1&pageSize=10&plantId={plant_id}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "token": self._token
        }
        async with self._session.get(url, headers=headers) as resp:
            return await resp.json()
