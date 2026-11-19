"""Writable numbers (sensoCOMFORT settings) for aroTHERM ebusd.

Every change goes through the coordinator's guarded writer: disabled unless
enabled in options, dry-run by default, bounds/step/max-change checked,
old value read first, result verified by reading back from the bus.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - New: summer temperature limit (10-25 C, step 1), holiday temperature (5-25 C).
  0.2.1 (2026-10-28) - Removed day temperature (z1DayTemp does not decode on this controller).
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - Optional: hot water target temperature (35-65 C, max 10 K per change).
"""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import WRITABLE_NUMBERS
from .const import DEVICE_CONTROLLER
from .coordinator import ArothermConfigEntry, ArothermCoordinator
from .entity import ArothermEntity

# translation key -> message key, is_temperature
NUMBERS: tuple[tuple[str, str, bool], ...] = (
    ("quick_veto_temp", "basv.z1QuickVetoTemp", True),
    ("night_temp", "basv.z1NightTemp", True),
    ("heat_curve", "basv.Hc1HeatCurve", False),
    ("min_flow_temp", "basv.Hc1MinFlowTempDesired", True),
    ("max_flow_temp", "basv.Hc1MaxFlowTempDesired", True),
    ("summer_temp_limit", "basv.Hc1SummerTempLimit", True),
    ("holiday_temp", "basv.z1HolidayTemp", True),
)
# only when hot water (DHW) is enabled in options
DHW_NUMBERS: tuple[tuple[str, str, bool], ...] = (
    ("hw_target_temp", "basv.HwcTempDesired", True),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArothermConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers."""
    coordinator = entry.runtime_data
    numbers = NUMBERS + (DHW_NUMBERS if coordinator.dhw else ())
    async_add_entities(ArothermNumber(coordinator, *n) for n in numbers)


class ArothermNumber(ArothermEntity, NumberEntity):
    """A sensoCOMFORT setting."""

    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: ArothermCoordinator, key: str, msg_key: str, is_temp: bool
    ) -> None:
        super().__init__(coordinator, key, DEVICE_CONTROLLER, msg_key)
        spec = WRITABLE_NUMBERS[msg_key]
        self._attr_native_min_value = spec.min_value
        self._attr_native_max_value = spec.max_value
        self._attr_native_step = spec.step
        if is_temp:
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        return self.coordinator.num(self._msg_key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(self._msg_key, value, entity_id=self.entity_id)
