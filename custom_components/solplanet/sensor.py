from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    plant_id = entry.data["plant_id"]

    async def update_data():
        return await api.fetch_inverter(plant_id)

    async_add_entities([
        SolplanetPowerSensor(api, plant_id, update_data),
        SolplanetEnergyTodaySensor(api, plant_id, update_data),
        SolplanetEnergyTotalSensor(api, plant_id, update_data),
    ])

class SolplanetBase(SensorEntity):
    def __init__(self, api, plant_id, update_func):
        self._api = api
        self._plant_id = plant_id
        self._update_func = update_func
        self._attr_available = False

    async def async_update(self):
        data = await self._update_func()
        if data and "result" in data:
            inv = data["result"]["records"][0]["invList"][0]
            self.handle_data(inv)

class SolplanetPowerSensor(SolplanetBase):
    _attr_name = "Solplanet Potência"
    _attr_device_class = "power"
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_state_class = "measurement"

    def handle_data(self, inv):
        self._attr_native_value = int(float(inv.get("pac", 0)) * 1000)
        self._attr_available = True

class SolplanetEnergyTodaySensor(SolplanetBase):
    _attr_name = "Solplanet Energia Hoje"
    _attr_device_class = "energy"
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_state_class = "total"

    def handle_data(self, inv):
        self._attr_native_value = float(inv.get("e_today", 0))
        self._attr_available = True

class SolplanetEnergyTotalSensor(SolplanetBase):
    _attr_name = "Solplanet Energia Total"
    _attr_device_class = "energy"
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_state_class = "total_increasing"

    def handle_data(self, inv):
        self._attr_native_value = float(inv.get("etotal", 0))
        self._attr_available = True
