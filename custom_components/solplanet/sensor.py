from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy, UnitOfPower
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    plant_id = hass.data[DOMAIN][entry.entry_id]["plant_id"]

    async def update_data():
        return await api.fetch_inverter(plant_id)

    async_add_entities([
        SolplanetPowerSensor(update_data),
        SolplanetEnergyTodaySensor(update_data),
        SolplanetEnergyTotalSensor(update_data),
    ])

class SolplanetBase(SensorEntity):
    def __init__(self, update_func):
        self._update_func = update_func
        self._attr_available = False

    async def async_update(self):
        data = await self._update_func()
        inv = data["result"]["records"][0]["invList"][0]
        self.handle_data(inv)
        self._attr_available = True

class SolplanetPowerSensor(SolplanetBase):
    _attr_name = "Solplanet Potência"
    _attr_device_class = "power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = "measurement"

    def handle_data(self, inv):
        self._attr_native_value = int(float(inv.get("pac", 0)) * 1000)

class SolplanetEnergyTodaySensor(SolplanetBase):
    _attr_name = "Solplanet Energia Hoje"
    _attr_device_class = "energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = "total"

    def handle_data(self, inv):
        self._attr_native_value = float(inv.get("e_today", 0))

class SolplanetEnergyTotalSensor(SolplanetBase):
    _attr_name = "Solplanet Energia Total"
    _attr_device_class = "energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = "total_increasing"

    def handle_data(self, inv):
        self._attr_native_value = float(inv.get("etotal", 0))
