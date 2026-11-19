"""Writable switches for aroTHERM ebusd.

Adaptive heating curve: basv AdaptHeatCurve (0=no, 1=yes). Written through
the coordinator's guarded writer, so it is read-only until writes are enabled.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.2.0 (2026-10-28) - New: adaptive heating curve switch.
  0.2.1 (2026-10-28) - Version bump only; no functional change.
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - Version bump only; no functional change.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEVICE_CONTROLLER
from .coordinator import ArothermConfigEntry, ArothermCoordinator
from .entity import ArothermEntity

# translation key -> message key; the message's values are "no"/"yes"
SWITCHES: tuple[tuple[str, str], ...] = (
    ("adaptive_heat_curve", "basv.AdaptHeatCurve"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArothermConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator = entry.runtime_data
    async_add_entities(ArothermSwitch(coordinator, *s) for s in SWITCHES)


class ArothermSwitch(ArothermEntity, SwitchEntity):
    """A yes/no controller setting."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ArothermCoordinator, key: str, msg_key: str) -> None:
        super().__init__(coordinator, key, DEVICE_CONTROLLER, msg_key)

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.field(self._msg_key)
        if value == "yes":
            return True
        if value == "no":
            return False
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write(self._msg_key, "yes", entity_id=self.entity_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write(self._msg_key, "no", entity_id=self.entity_id)
