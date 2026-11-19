"""Base entity for aroTHERM ebusd.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Version bump only; no functional change.
  0.2.1 (2026-10-28) - Availability uses the signal grace period; removed deprecated via_device.
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - Version bump only; no functional change.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_CONTROLLER, DEVICE_EBUSD, DEVICE_HEATPUMP, DOMAIN
from .coordinator import ArothermCoordinator

_ADDR = {DEVICE_HEATPUMP: "08", DEVICE_CONTROLLER: "15"}
_NAMES = {
    DEVICE_HEATPUMP: ("aroTHERM plus", "Vaillant"),
    DEVICE_CONTROLLER: ("sensoCOMFORT VRC 720", "Vaillant"),
    DEVICE_EBUSD: ("ebusd", "ebusd.eu"),
}


def device_info(coordinator: ArothermCoordinator, device: str) -> DeviceInfo:
    """Build DeviceInfo for one of the three devices."""
    entry = coordinator.config_entry
    name, maker = _NAMES[device]
    info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{device}")},
        name=name,
        manufacturer=maker,
    )
    if device == DEVICE_EBUSD:
        info["sw_version"] = coordinator.status.version
        info["configuration_url"] = (
            f"http://{entry.data['host']}:{entry.data.get('http_port') or 8889}/data"
        )
    else:
        scanned = coordinator.status.info.get("devices", {}).get(_ADDR[device], {})
        if scanned.get("ID"):
            info["model"] = scanned["ID"]
        if scanned.get("SW"):
            info["sw_version"] = scanned["SW"]
        if scanned.get("HW"):
            info["hw_version"] = scanned["HW"]
    return info


class ArothermEntity(CoordinatorEntity[ArothermCoordinator]):
    """Common base."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ArothermCoordinator,
        key: str,
        device: str,
        msg_key: str | None = None,
        bus: bool = True,
    ) -> None:
        super().__init__(coordinator)
        self._msg_key = msg_key
        self._bus = bus
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(coordinator, device)

    @property
    def available(self) -> bool:
        """Unavailable if ebusd is down, the bus has no signal, or the value is stale."""
        if not super().available:
            return False
        if self._bus and not self.coordinator.bus_ok():
            return False
        if self._msg_key is not None and not self.coordinator.is_fresh(self._msg_key):
            return False
        return True
