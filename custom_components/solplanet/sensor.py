from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import (
    CONF_PLANT_ID,
    COORDINATOR,
    DOMAIN,
    RUNTIME_STATUS,
    STATUS_AUTH_EXPIRED,
    STATUS_CONNECTION_ERROR,
    STATUS_OK,
)


@dataclass(frozen=True, kw_only=True)
class SolplanetSensorDescription(SensorEntityDescription):
    value_key: str


SENSOR_DESCRIPTIONS: tuple[SolplanetSensorDescription, ...] = (
    SolplanetSensorDescription(
        key="pac",
        name="Solplanet Potência",
        value_key="pac",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="e_today",
        name="Solplanet Energia Hoje",
        value_key="e_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SolplanetSensorDescription(
        key="etotal",
        name="Solplanet Energia Total",
        value_key="etotal",
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
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: DataUpdateCoordinator = data[COORDINATOR]
    runtime_status: dict[str, str] = data[RUNTIME_STATUS]

    entities: list[SensorEntity] = [
        SolplanetSensor(
            coordinator=coordinator,
            entry=entry,
            description=description,
            runtime_status=runtime_status,
        )
        for description in SENSOR_DESCRIPTIONS
    ]
    entities.append(
        SolplanetApiStatusSensor(
            coordinator=coordinator,
            entry=entry,
            runtime_status=runtime_status,
        )
    )

    async_add_entities(entities)


class SolplanetBaseEntity(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._plant_id = entry.data[CONF_PLANT_ID]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._plant_id)},
            manufacturer="Solplanet",
            name=f"Solplanet Plant {self._plant_id}",
        )


class SolplanetSensor(SolplanetBaseEntity):
    entity_description: SolplanetSensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: SolplanetSensorDescription,
        runtime_status: dict[str, str],
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._runtime_status = runtime_status
        self._attr_unique_id = f"solplanet_{self._plant_id}_{description.key}"

    @property
    def available(self) -> bool:
        if self.entity_description.state_class == SensorStateClass.MEASUREMENT:
            return (
                self._runtime_status.get("status") == STATUS_OK
                and self._inverter_data is not None
            )
        return self._inverter_data is not None

    @property
    def native_value(self) -> int | float | None:
        inv = self._inverter_data
        if inv is None:
            return None

        if self.entity_description.value_key == "pac":
            return int(float(inv.get("pac", 0)) * 1000)

        return float(inv.get(self.entity_description.value_key, 0))

    @property
    def _inverter_data(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        if not data:
            return None

        try:
            return data["result"]["records"][0]["invList"][0]
        except (KeyError, IndexError, TypeError):
            return None


class SolplanetApiStatusSensor(SolplanetBaseEntity):
    _attr_name = "Solplanet Status API"
    _attr_icon = "mdi:shield-check"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATUS_OK, STATUS_AUTH_EXPIRED, STATUS_CONNECTION_ERROR, "unknown"]

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        runtime_status: dict[str, str],
    ) -> None:
        super().__init__(coordinator, entry)
        self._runtime_status = runtime_status
        self._attr_unique_id = f"solplanet_{self._plant_id}_api_status"

    @property
    def native_value(self) -> str:
        return self._runtime_status.get("status", "unknown")
