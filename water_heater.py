"""Hot water (DHW) water heater entity for aroTHERM ebusd.

Created only when "Hot water (DHW) installed" is switched on in the options.

Mapping:
  current temperature -> basv HwcStorageTemp (cylinder sensor),
                         falling back to hmu HwcTemp (heat pump's DHW sensor)
  target temperature  -> basv HwcTempDesired (writable, 35-65 C, max 10 K/change)
  operation mode      -> basv HwcOpMode: off / auto / day / night (writable)

All writes go through the coordinator's guarded writer (off by default,
dry run, limits, read-back verification, logbook).
NOT verified on live hardware: the system it was developed on has no
cylinder. Message names and value lists come from the ebusd definitions.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.3.0 (2026-10-28) - New: optional hot water (DHW) water heater entity.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import HWC_OPMODE_OPTIONS, WRITABLE_NUMBERS
from .const import DEVICE_CONTROLLER
from .coordinator import ArothermConfigEntry, ArothermCoordinator
from .entity import ArothermEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArothermConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the hot water entity (only if DHW is enabled)."""
    coordinator = entry.runtime_data
    if coordinator.dhw:
        async_add_entities([ArothermWaterHeater(coordinator)])


class ArothermWaterHeater(ArothermEntity, WaterHeaterEntity):
    """Domestic hot water cylinder."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = list(HWC_OPMODE_OPTIONS)

    def __init__(self, coordinator: ArothermCoordinator) -> None:
        super().__init__(coordinator, "hot_water", DEVICE_CONTROLLER, "basv.HwcOpMode")
        spec = WRITABLE_NUMBERS["basv.HwcTempDesired"]
        self._attr_min_temp = spec.min_value
        self._attr_max_temp = spec.max_value

    @property
    def current_temperature(self) -> float | None:
        temp = self.coordinator.num("basv.HwcStorageTemp")
        return temp if temp is not None else self.coordinator.num("hmu.HwcTemp")

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.num("basv.HwcTempDesired")

    @property
    def current_operation(self) -> str | None:
        mode = self.coordinator.field("basv.HwcOpMode")
        return mode if mode in HWC_OPMODE_OPTIONS else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.coordinator.field("hmu.Statuscode")
        return {
            "special_function": self.coordinator.field("basv.HwcSFMode"),
            "heat_pump_hot_water_mode": self.coordinator.field("hmu.HwcMode"),
            "charging": isinstance(status, str) and status.startswith("Warm Water:")
            and "active" in status,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.coordinator.async_write(
                "basv.HwcTempDesired", float(temp), entity_id=self.entity_id
            )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await self.coordinator.async_write(
            "basv.HwcOpMode", operation_mode, entity_id=self.entity_id
        )
