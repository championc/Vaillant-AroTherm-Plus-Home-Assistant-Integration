"""Config flow for aroTHERM ebusd (host and ports in the UI, no YAML).

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Version bump only; no functional change.
  0.2.1 (2026-10-28) - Version bump only; no functional change.
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - New option: Hot water (DHW) installed.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .const import (
    CONF_DHW,
    CONF_HTTP_PORT,
    CONF_LOW_PRESSURE,
    CONF_SC_MIN_RUN,
    CONF_SC_STARTS,
    CONF_TCP_PORT,
    CONF_TIER_FAST,
    CONF_TIER_FLOW,
    CONF_TIER_HOURLY,
    CONF_TIER_MEDIUM,
    CONF_TIER_SLOW,
    CONF_WRITE_DRY_RUN,
    CONF_WRITES_ENABLED,
    DEFAULT_HTTP_PORT,
    DEFAULT_OPTIONS,
    DEFAULT_TCP_PORT,
    DOMAIN,
)
from .ebusd_client import EbusdConnectionError, EbusdHttpClient, EbusdTcpClient

_LOGGER = logging.getLogger(__name__)


def _conn_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_TCP_PORT, default=defaults.get(CONF_TCP_PORT, DEFAULT_TCP_PORT)):
                vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(CONF_HTTP_PORT, default=defaults.get(CONF_HTTP_PORT, DEFAULT_HTTP_PORT)):
                vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
        }
    )


async def _validate(hass, data: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    """Check ebusd answers on TCP (required) and HTTP (optional). Read-only."""
    errors: dict[str, str] = {}
    info: dict[str, Any] = {}
    tcp = EbusdTcpClient(data[CONF_HOST], data[CONF_TCP_PORT], timeout=8)
    try:
        info = await tcp.info()
    except EbusdConnectionError as err:
        _LOGGER.debug("TCP check failed: %s", err)
        errors["base"] = "cannot_connect"
        return errors, info
    finally:
        await tcp.close()
    if "version" not in info or "ebusd" not in str(info.get("version")):
        errors["base"] = "not_ebusd"
        return errors, info
    if not any(d.get("ID", "").startswith("HMU") for d in info["devices"].values()):
        errors["base"] = "no_heatpump"
        return errors, info
    if data[CONF_HTTP_PORT]:
        http = EbusdHttpClient(async_get_clientsession(hass), data[CONF_HOST], data[CONF_HTTP_PORT], 8)
        try:
            await http.get_circuit("broadcast")
        except EbusdConnectionError as err:
            _LOGGER.debug("HTTP check failed: %s", err)
            errors[CONF_HTTP_PORT] = "http_failed"
    return errors, info


class ArothermConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_TCP_PORT]}")
            self._abort_if_unique_id_configured()
            errors, _info = await _validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="aroTHERM plus (ebusd)", data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_conn_schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, _info = await _validate(self.hass, user_input)
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_conn_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> ArothermOptionsFlow:
        return ArothermOptionsFlow()


def _secs(lo: int, hi: int) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(min=lo, max=hi, step=1, unit_of_measurement="s",
                                      mode=selector.NumberSelectorMode.BOX)
    )


class ArothermOptionsFlow(OptionsFlow):
    """Polling, thresholds and write safety."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            clean = {k: (int(v) if k not in (CONF_LOW_PRESSURE, CONF_WRITES_ENABLED,
                                             CONF_WRITE_DRY_RUN, CONF_DHW) else v)
                     for k, v in user_input.items()}
            return self.async_create_entry(data=clean)
        cur = {**DEFAULT_OPTIONS, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_TIER_FAST, default=cur[CONF_TIER_FAST]): _secs(10, 300),
                vol.Required(CONF_TIER_FLOW, default=cur[CONF_TIER_FLOW]): _secs(10, 600),
                vol.Required(CONF_TIER_MEDIUM, default=cur[CONF_TIER_MEDIUM]): _secs(15, 900),
                vol.Required(CONF_TIER_SLOW, default=cur[CONF_TIER_SLOW]): _secs(60, 3600),
                vol.Required(CONF_TIER_HOURLY, default=cur[CONF_TIER_HOURLY]): _secs(600, 86400),
                vol.Required(CONF_SC_STARTS, default=cur[CONF_SC_STARTS]): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=20, step=1,
                                                  mode=selector.NumberSelectorMode.BOX)),
                vol.Required(CONF_SC_MIN_RUN, default=cur[CONF_SC_MIN_RUN]): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=120, step=1, unit_of_measurement="min",
                                                  mode=selector.NumberSelectorMode.BOX)),
                vol.Required(CONF_LOW_PRESSURE, default=cur[CONF_LOW_PRESSURE]): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.3, max=2.5, step=0.1, unit_of_measurement="bar",
                                                  mode=selector.NumberSelectorMode.BOX)),
                vol.Required(CONF_WRITES_ENABLED, default=cur[CONF_WRITES_ENABLED]): bool,
                vol.Required(CONF_WRITE_DRY_RUN, default=cur[CONF_WRITE_DRY_RUN]): bool,
                vol.Required(CONF_DHW, default=cur[CONF_DHW]): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
