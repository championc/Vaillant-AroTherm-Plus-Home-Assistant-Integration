"""Diagnostics download for aroTHERM ebusd.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Version bump only; no functional change.
  0.2.1 (2026-10-28) - Version bump only; no functional change.
  0.2.2 (2026-10-28) - Per-message rejected_count and last_rejected.
  0.3.0 (2026-10-28) - Shows whether hot water is enabled; lists only the messages being polled.
"""

from __future__ import annotations

from dataclasses import asdict
import time
from typing import Any

from homeassistant.core import HomeAssistant

from .const import VERSION
from .coordinator import ArothermConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ArothermConfigEntry
) -> dict[str, Any]:
    """Return diagnostics (contains no credentials: ebusd has none here)."""
    c = entry.runtime_data
    now = time.time()
    messages = {}
    for m in c.messages:
        st = c.msgs[m.key]
        messages[m.key] = {
            "tier": m.tier,
            "values": st.values,
            "age_s": None if st.updated is None else round(now - st.updated, 1),
            "fresh": c.is_fresh(m.key),
            "ok_count": st.ok_count,
            "error_count": st.error_count,
            "last_error": st.error,
            "rejected_count": st.rejected_count,
            "last_rejected": st.last_rejected,
        }
    return {
        "integration_version": VERSION,
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "effective_options": c.options,
        "ebusd": {**asdict(c.status)},
        "bus_reads_last_minute": c.bus_reads_per_minute(),
        "compressor_running": c.compressor_running(),
        "hot_water_enabled": c.dhw,
        "derived": c.derived.to_dict(),
        "messages": messages,
        "write_log": list(c.write_log),
        "last_update_success": c.last_update_success,
    }
