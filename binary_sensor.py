"""Binary sensors for aroTHERM ebusd.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Version bump only; no functional change.
  0.2.1 (2026-10-28) - Version bump only; no functional change.
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - Optional: hot water charging, hot water mode active.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import STATE00_COMPRESSORSTATE, STATE00_DEFROST, STATE01_PUMPSTATE
from .const import CONF_LOW_PRESSURE, DEVICE_EBUSD, DEVICE_HEATPUMP
from .coordinator import ArothermConfigEntry, ArothermCoordinator
from .entity import ArothermEntity


@dataclass(frozen=True, kw_only=True)
class ArothermBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description."""

    device: str = DEVICE_HEATPUMP
    dhw: bool = False
    msg: str | None = None
    bus: bool = True
    always_available: bool = False
    value_fn: Callable[[ArothermCoordinator], bool | None]


def _defrost(c: ArothermCoordinator) -> bool | None:
    flag = c.field("hmu.State00", STATE00_DEFROST)
    cstate = c.field("hmu.State00", STATE00_COMPRESSORSTATE)
    status = c.field("hmu.Statuscode")
    votes = []
    if isinstance(flag, str):
        votes.append(flag == "active")
    if isinstance(cstate, str):
        votes.append(cstate == "Defrosting")
    if isinstance(status, str):
        votes.append(status == "Deicing active")
    return any(votes) if votes else None


def _pump(c: ArothermCoordinator) -> bool | None:
    state = c.field("hmu.State01", STATE01_PUMPSTATE)
    if isinstance(state, str):
        return state not in ("off",)
    cir = c.field("hmu.StatusCirPump")
    if isinstance(cir, str):
        return cir == "on"
    return None


def _hw_charging(c: ArothermCoordinator) -> bool | None:
    status = c.field("hmu.Statuscode")
    if not isinstance(status, str):
        return None
    return status.startswith("Warm Water:") and "active" in status


def _hw_mode_active(c: ArothermCoordinator) -> bool | None:
    v = c.field("hmu.HwcModeActive")
    return None if not isinstance(v, str) else v == "yes"


def _fault(c: ArothermCoordinator) -> bool | None:
    hp, ctrl = c.errors("hmu"), c.errors("basv")
    if hp is None and ctrl is None:
        return None
    return bool(hp) or bool(ctrl)


def _low_pressure(c: ArothermCoordinator) -> bool | None:
    p = c.num("hmu.FlowPressure")
    return None if p is None else p < float(c.options[CONF_LOW_PRESSURE])


BINARY_SENSORS: tuple[ArothermBinaryDescription, ...] = (
    ArothermBinaryDescription(key="compressor_running", device_class=BinarySensorDeviceClass.RUNNING,
                              value_fn=lambda c: c.compressor_running()),
    ArothermBinaryDescription(key="defrost", value_fn=_defrost),
    ArothermBinaryDescription(key="heating_pump", device_class=BinarySensorDeviceClass.RUNNING,
                              value_fn=_pump),
    ArothermBinaryDescription(key="fault", device_class=BinarySensorDeviceClass.PROBLEM,
                              value_fn=_fault),
    ArothermBinaryDescription(key="low_water_pressure", msg="hmu.FlowPressure",
                              device_class=BinarySensorDeviceClass.PROBLEM, value_fn=_low_pressure),
    ArothermBinaryDescription(key="short_cycling", device_class=BinarySensorDeviceClass.PROBLEM,
                              value_fn=lambda c: c.derived.short_cycling(time.time())),
    ArothermBinaryDescription(key="hw_charging", dhw=True, device_class=BinarySensorDeviceClass.HEAT,
                              value_fn=_hw_charging),
    ArothermBinaryDescription(key="hw_mode_active", dhw=True, msg="hmu.HwcModeActive",
                              value_fn=_hw_mode_active),
    ArothermBinaryDescription(key="ebus_signal", device=DEVICE_EBUSD, bus=False,
                              device_class=BinarySensorDeviceClass.CONNECTIVITY,
                              entity_category=EntityCategory.DIAGNOSTIC,
                              value_fn=lambda c: c.status.signal),
    ArothermBinaryDescription(key="ebusd_connected", device=DEVICE_EBUSD, bus=False,
                              always_available=True,
                              device_class=BinarySensorDeviceClass.CONNECTIVITY,
                              entity_category=EntityCategory.DIAGNOSTIC,
                              value_fn=lambda c: c.last_update_success and c.status.reachable),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArothermConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ArothermBinarySensor(coordinator, d) for d in BINARY_SENSORS if coordinator.dhw or not d.dhw
    )


class ArothermBinarySensor(ArothermEntity, BinarySensorEntity):
    """Binary sensor."""

    entity_description: ArothermBinaryDescription

    def __init__(self, coordinator: ArothermCoordinator, desc: ArothermBinaryDescription) -> None:
        super().__init__(coordinator, desc.key, desc.device, desc.msg, desc.bus)
        self.entity_description = desc

    @property
    def available(self) -> bool:
        if self.entity_description.always_available:
            return True
        return super().available

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator)
