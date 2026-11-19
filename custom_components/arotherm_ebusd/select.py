"""Writable selects (sensoCOMFORT modes) for aroTHERM ebusd.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - New: setback mode (eco/night).
  0.2.1 (2026-10-28) - Version bump only; no functional change.
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - Optional: hot water mode, hot water special function (auto/load), heat pump hot water mode.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import WRITABLE_SELECTS
from .const import DEVICE_CONTROLLER, DEVICE_HEATPUMP
from .coordinator import ArothermConfigEntry, ArothermCoordinator
from .entity import ArothermEntity

SELECTS: tuple[tuple[str, str], ...] = (
    ("zone_mode", "basv.z1OpMode"),
    ("zone_special_function", "basv.z1SFMode"),
    ("room_temp_modulation", "basv.Hc1RoomTempSwitchOn"),
    ("setback_mode", "basv.Hc1AutoOffMode"),
)
# only when hot water (DHW) is enabled in options
DHW_SELECTS: tuple[tuple[str, str], ...] = (
    ("hw_op_mode", "basv.HwcOpMode"),
    ("hw_special_function", "basv.HwcSFMode"),
    ("hw_hp_mode", "hmu.HwcMode"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArothermConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects."""
    coordinator = entry.runtime_data
    selects = SELECTS + (DHW_SELECTS if coordinator.dhw else ())
    async_add_entities(ArothermSelect(coordinator, *s) for s in selects)


class ArothermSelect(ArothermEntity, SelectEntity):
    """A sensoCOMFORT mode."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ArothermCoordinator, key: str, msg_key: str) -> None:
        device = DEVICE_HEATPUMP if msg_key.startswith("hmu.") else DEVICE_CONTROLLER
        super().__init__(coordinator, key, device, msg_key)
        self._attr_options = list(WRITABLE_SELECTS[msg_key])

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.field(self._msg_key)
        return value if value in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write(self._msg_key, option, entity_id=self.entity_id)
