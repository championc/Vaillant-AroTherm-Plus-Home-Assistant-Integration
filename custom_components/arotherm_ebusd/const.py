"""Constants for the aroTHERM ebusd integration.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - VERSION 0.2.0.
  0.2.1 (2026-10-28) - VERSION 0.2.1; SIGNAL_GRACE = 120 s.
  0.2.2 (2026-10-28) - VERSION 0.2.2.
  0.3.0 (2026-10-28) - VERSION 0.3.0; CONF_DHW option.
"""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "arotherm_ebusd"
VERSION: Final = "0.3.0"

# --- config entry data -------------------------------------------------------
CONF_TCP_PORT: Final = "tcp_port"
CONF_HTTP_PORT: Final = "http_port"

DEFAULT_TCP_PORT: Final = 8888
DEFAULT_HTTP_PORT: Final = 8889  # 0 disables HTTP; TCP is then used for everything

# --- options -----------------------------------------------------------------
CONF_TIER_FAST: Final = "tier_fast"
CONF_TIER_FLOW: Final = "tier_flow"
CONF_TIER_MEDIUM: Final = "tier_medium"
CONF_TIER_SLOW: Final = "tier_slow"
CONF_TIER_HOURLY: Final = "tier_hourly"
CONF_SC_STARTS: Final = "short_cycle_starts_per_hour"
CONF_SC_MIN_RUN: Final = "short_cycle_min_run_minutes"
CONF_LOW_PRESSURE: Final = "low_pressure_bar"
CONF_WRITES_ENABLED: Final = "writes_enabled"
CONF_WRITE_DRY_RUN: Final = "write_dry_run"
CONF_DHW: Final = "hot_water_installed"

TIER_FAST: Final = "fast"
TIER_FLOW: Final = "flow"
TIER_MEDIUM: Final = "medium"
TIER_SLOW: Final = "slow"
TIER_HOURLY: Final = "hourly"
TIER_PASSIVE: Final = "passive"

TIER_OPTION: Final = {
    TIER_FAST: CONF_TIER_FAST,
    TIER_FLOW: CONF_TIER_FLOW,
    TIER_MEDIUM: CONF_TIER_MEDIUM,
    TIER_SLOW: CONF_TIER_SLOW,
    TIER_HOURLY: CONF_TIER_HOURLY,
}

DEFAULT_OPTIONS: Final = {
    CONF_TIER_FAST: 15,
    CONF_TIER_FLOW: 30,
    CONF_TIER_MEDIUM: 60,
    CONF_TIER_SLOW: 300,
    CONF_TIER_HOURLY: 3600,
    CONF_SC_STARTS: 3,
    CONF_SC_MIN_RUN: 10,
    CONF_LOW_PRESSURE: 1.0,
    CONF_WRITES_ENABLED: False,
    CONF_WRITE_DRY_RUN: True,
    CONF_DHW: False,
}

# Passive/cached messages: refreshed by other bus masters (VRC 720, VWZIO).
# We look at ebusd's cache every PASSIVE_INTERVAL seconds and only ask ebusd
# to fetch from the bus if the cached value is older than PASSIVE_MAXAGE.
# Short eBUS signal dropouts (seen ~10x/hour on this bus, 15-60 s each) do not
# make bus entities unavailable unless the signal stays lost this long.
SIGNAL_GRACE: Final = 120.0

PASSIVE_INTERVAL: Final = 60
PASSIVE_MAXAGE: Final = 900

# Value ebusd reports for sensors that are not fitted.
SENTINEL_VALUES: Final = (-99.0,)

# Minimum seconds between two writes (any message).
WRITE_MIN_INTERVAL: Final = 5.0

# Derived-value persistence
STORAGE_VERSION: Final = 1
STORAGE_SAVE_DELAY: Final = 60

# Devices
DEVICE_HEATPUMP: Final = "heatpump"
DEVICE_CONTROLLER: Final = "controller"
DEVICE_EBUSD: Final = "ebusd"
