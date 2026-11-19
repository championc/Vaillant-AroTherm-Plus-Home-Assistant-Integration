"""Climate entity for sensoCOMFORT zone 1.

Mapping (z1OpMode): off -> OFF, auto -> AUTO, day -> HEAT, night -> HEAT
(night is shown via the 'zone mode' select).
Setting a temperature:
  * mode 'day'  -> refused: z1DayTemp does not decode on this VRC 720
                   ("ERR: invalid position in decode"), so it cannot be set
  * mode 'auto' -> writes z1QuickVetoTemp, then z1SFMode = veto
  * mode 'off'/'night' -> refused
The quick-veto sequence is EXPERIMENTAL: how the VRC 720 treats an
eBUS-initiated veto (duration, cancellation) is not verified yet; test it
in dry-run mode first.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Writes pass entity_id for the logbook.
  0.2.1 (2026-10-28) - Setting a temperature in day (manual) mode is refused; z1DayTemp is not usable.
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - Version bump only; no functional change.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import WRITABLE_NUMBERS
from .const import DEVICE_CONTROLLER
from .coordinator import ArothermConfigEntry, ArothermCoordinator
from .entity import ArothermEntity

_TO_HVAC = {"off": HVACMode.OFF, "auto": HVACMode.AUTO, "day": HVACMode.HEAT, "night": HVACMode.HEAT}
_FROM_HVAC = {HVACMode.OFF: "off", HVACMode.AUTO: "auto", HVACMode.HEAT: "day"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArothermConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the zone 1 climate entity."""
    async_add_entities([ArothermZoneClimate(entry.runtime_data)])


class ArothermZoneClimate(ArothermEntity, ClimateEntity):
    """sensoCOMFORT zone 1."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, coordinator: ArothermCoordinator) -> None:
        super().__init__(coordinator, "zone1", DEVICE_CONTROLLER, "basv.z1OpMode")
        spec = WRITABLE_NUMBERS["basv.z1QuickVetoTemp"]
        self._attr_min_temp = spec.min_value
        self._attr_max_temp = spec.max_value
        self._attr_target_temperature_step = spec.step

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.num("basv.z1RoomTemp")

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.num("basv.z1ActualRoomTempDesired")

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = self.coordinator.field("basv.z1OpMode")
        return _TO_HVAC.get(mode) if isinstance(mode, str) else None

    @property
    def hvac_action(self) -> HVACAction | None:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        running = self.coordinator.compressor_running()
        if running is None:
            return None
        return HVACAction.HEATING if running else HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "zone_mode": self.coordinator.field("basv.z1OpMode"),
            "special_function": self.coordinator.field("basv.z1SFMode"),
        }

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.async_write(
            "basv.z1OpMode", _FROM_HVAC[hvac_mode], entity_id=self.entity_id
        )

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        mode = self.coordinator.field("basv.z1OpMode")
        if mode == "auto":
            await self.coordinator.async_write(
                "basv.z1QuickVetoTemp", float(temp), entity_id=self.entity_id
            )
            await self.coordinator.async_write(
                "basv.z1SFMode", "veto", chained=True, entity_id=self.entity_id
            )
        else:
            raise HomeAssistantError(
                f"Zone mode is '{mode}': switch to auto or heat before setting a temperature"
            )
