from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import CONF_PLANT_ID, COORDINATOR, DOMAIN


@dataclass(frozen=True, kw_only=True)
class SolplanetSensorDescription:
    key: str
    name: str
    native_unit_of_measurement: str
    device_class: SensorDeviceClass
    state_class: SensorStateClass


SENSOR_DESCRIPTIONS = (
    SolplanetSensorDescription(
        key="pac",
        name="Potência",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="e_today",
        name="Energia Hoje",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SolplanetSensorDescription(
        key="etotal",
        name="Energia Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    async_add_entities(
        SolplanetSensor(
            coordinator=coordinator,
            entry=entry,
            description=description,
        )
        for description in SENSOR_DESCRIPTIONS
    )


class SolplanetSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SolplanetSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._plant_id = entry.data[CONF_PLANT_ID]
        self._attr_name = f"Solplanet {description.name}"
        self._attr_unique_id = f"solplanet_{self._plant_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._plant_id)},
            manufacturer="Solplanet",
            name=f"Solplanet Plant {self._plant_id}",
        )

    @property
    def native_value(self):
        inv = self._inverter_data
        if self.entity_description.key == "pac":
            return int(float(inv.get("pac", 0)) * 1000)
        return float(inv.get(self.entity_description.key, 0))

    @property
    def _inverter_data(self) -> dict:
        data = self.coordinator.data or {}
        return data["result"]["records"][0]["invList"][0]
