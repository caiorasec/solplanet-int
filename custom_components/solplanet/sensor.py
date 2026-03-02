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
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
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
    convert_kw_to_w: bool = False


SENSOR_DESCRIPTIONS: tuple[SolplanetSensorDescription, ...] = (
    SolplanetSensorDescription(
        key="pac",
        name="Solplanet Potência",
        value_key="pac",
        convert_kw_to_w=True,
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
    SolplanetSensorDescription(
        key="fac",
        name="Solplanet Frequência AC",
        value_key="fac",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="vac_1",
        name="Solplanet Tensão AC L1",
        value_key="vac_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="iac_1",
        name="Solplanet Corrente AC L1",
        value_key="iac_1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="tmp",
        name="Solplanet Temperatura",
        value_key="tmp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="pf",
        name="Solplanet Fator de Potência",
        value_key="pf",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="vpv_1",
        name="Solplanet Tensão PV 1",
        value_key="vpv_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="vpv_2",
        name="Solplanet Tensão PV 2",
        value_key="vpv_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="vpv_3",
        name="Solplanet Tensão PV 3",
        value_key="vpv_3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="ipv_1",
        name="Solplanet Corrente PV 1",
        value_key="ipv_1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="ipv_2",
        name="Solplanet Corrente PV 2",
        value_key="ipv_2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="ipv_3",
        name="Solplanet Corrente PV 3",
        value_key="ipv_3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolplanetSensorDescription(
        key="flg",
        name="Solplanet Estado Inversor (flg)",
        value_key="flg",
    ),
    SolplanetSensorDescription(
        key="wan",
        name="Solplanet Warning Code",
        value_key="wan",
    ),
    SolplanetSensorDescription(
        key="err",
        name="Solplanet Error Code",
        value_key="err",
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
        inv = self._inverter_data
        if inv is None:
            return False
        if self.entity_description.value_key not in inv:
            return False
        if self.entity_description.state_class == SensorStateClass.MEASUREMENT:
            return self._runtime_status.get("status") == STATUS_OK
        return True

    @property
    def native_value(self) -> int | float | None:
        inv = self._inverter_data
        if inv is None:
            return None

        raw_value = inv.get(self.entity_description.value_key)
        if raw_value is None:
            return None

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None

        if self.entity_description.convert_kw_to_w:
            return int(value * 1000)

        if value.is_integer():
            return int(value)
        return value

    @property
    def _inverter_data(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        if not data:
            return None

        try:
            return data["result"]["records"][0]["invList"][0]
        except (KeyError, IndexError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        inv = self._inverter_data
        if not inv:
            return None

        attrs: dict[str, Any] = {}
        if inv.get("sn"):
            attrs["inverter_sn"] = inv["sn"]
        if inv.get("model"):
            attrs["inverter_model"] = inv["model"]
        return attrs or None


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
