# Vaillant-AroTherm-Plus-Home-Assistant-Integration
Vaillant AroTherm Plus Home Assistant Integration

arotherm_ebusd README - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Documented the new writable settings, read-only values and logbook entries.
  0.2.1 (2026-10-28) - Signal grace period, removed day temperature, bus dropout note.
  0.2.1 r2 (2026-10-28) - Rewritten after the live install: real entity IDs, verified
                          values, write-test result, known issues found on the live bus
                          (signal dropouts, corrupted values).
  0.2.2 (2026-10-28) - Plausibility checks against corrupted bus values; compressor-running
                       rule; updated status, known issues and changelog.
  0.3.0 (2026-10-28) - Optional hot water (DHW) support: option, entities, settings,
                       COP change, unverified-on-hardware note.
-->

# aroTHERM ebusd

A local Home Assistant integration for a **Vaillant aroTHERM plus 5 kW** monobloc heat pump with a
**sensoCOMFORT VRC 720**, read and written through **ebusd**. It uses TCP 8888 for reads and writes, and HTTP/JSON 8889 for ebusd's cache.
No cloud and no MQTT.

It is built for one installation:

| Part | Detail |
|---|---|
| ebusd | 26.1, Docker on 192.168.1.22, message definitions `ebusd-2.1.x/en` |
| eBUS adapter | Adapter Shield v5/C6 at 192.168.1.25:9999 (enhanced), firmware 1.1[6911] |
| Heat pump | `HMU00`, SW 0902 / HW 5103, eBUS address 08 |
| Controller | `BASV3` (sensoCOMFORT VRC 720), SW 0760 / HW 7304, address 15 |
| Also on the bus | `VWZIO` at address 76: all its sensors read −0.1 / −99, so it is ignored |
| Home Assistant | 2026.10.4, HA Container |

Every message name it uses was taken from that ebusd's own definitions; the unit tests check this.

## Status (28 Oct 2026)

| Check | Result |
|---|---|
| Installed version | **0.2.1** live; **0.3.0** ready to install (plausibility checks + optional hot water support) |
| Values vs ebusd's own MQTT entities | match: flow 32.44 = 32.44 °C, heat 2.3 = 2.3 kW, input 437.6 = 437.6 W, status identical |
| Bus load | ~15 reads/min |
| Dry-run write | `write -c basv z1HolidayTemp 14.5` shown and logged; nothing sent ✔ |
| Real write | 15 → 14.5 → 15, both answered `done` and verified by reading back from the controller ✔ |
| Writes | **enabled, dry run off** (as of 14:23) |

## Devices and entities

There are three devices: **aroTHERM plus**, **sensoCOMFORT VRC 720** and **ebusd**.
Entities added in 0.2.0 got a `heating_` prefix because the devices are in the *Heating* area.

### aroTHERM plus: main sensors
| Entity | What it is | Source |
|---|---|---|
| `sensor.arotherm_plus_flow_temperature` | Flow temperature, °C | `hmu FlowTemp`, every 30 s |
| `sensor.arotherm_plus_return_temperature` | Return temperature, °C | `hmu ReturnTemp`, every 30 s |
| `sensor.arotherm_plus_flow_return_difference` | Flow − return, K | calculated |
| `sensor.arotherm_plus_requested_flow_temperature` | Flow temperature the controller is asking for, °C | `hmu SetMode` (passive) |
| `sensor.arotherm_plus_water_flow_rate` | Water flow, L/h | `hmu WaterThroughput`, every 30 s |
| `sensor.arotherm_plus_system_water_pressure` | Heating water pressure, bar | `hmu FlowPressure`, every 5 min |
| `sensor.arotherm_plus_heat_output` | Heat output, kW (heat pump's figure, 0.1 kW steps) | `hmu CurrentYieldPower`, every 15 s |
| `sensor.arotherm_plus_electrical_input` | Electrical input, W (heat pump's own estimate) | `hmu CurrentConsumedPowerWatt`, every 15 s |
| `sensor.arotherm_plus_compressor_modulation` | Compressor modulation, % | every 60 s |
| `sensor.arotherm_plus_compressor_speed` | Compressor speed, rps | every 60 s |
| `sensor.arotherm_plus_energy_integral` | Energy integral, °min (compressor starts at −100) | every 60 s |
| `sensor.arotherm_plus_status` | Status, e.g. "Heating: Compressor active" (53 states) | `hmu Statuscode`, every 60 s |
| `sensor.arotherm_plus_outside_temperature` | Outside temperature, °C | broadcast (passive) |
| `sensor.arotherm_plus_air_intake_temperature` | Air intake temperature, °C | every 5 min |
| `sensor.arotherm_plus_heating_pump_power` | Heating pump power, % | every 5 min |
| `sensor.arotherm_plus_heat_pump_active_errors` | Number of active errors (codes in attributes) | `hmu currenterror`, every 5 min |

### aroTHERM plus: energy and counters
| Entity | What it is |
|---|---|
| `sensor.arotherm_plus_heat_produced_lifetime` / `_today` / `_this_month` | Heat produced, kWh (heat pump counters) |
| `sensor.arotherm_plus_electricity_used_lifetime_reported` | Electricity used, kWh (heat pump counter, whole kWh only) |
| `sensor.arotherm_plus_environmental_energy_today` | Energy taken from the air today, kWh (passive) |
| `sensor.arotherm_plus_compressor_starts_lifetime`, `_compressor_hours` | Compressor starts and hours |
| `sensor.arotherm_plus_heating_pump_hours`, `_heating_pump_starts`, `_fan_hours`, `_fan_starts`, `_heat_pump_operating_hours` | Counters (diagnostic) |
| `sensor.arotherm_plus_cop_reported_by_heat_pump`, `_cop_this_month_reported_by_heat_pump` | The heat pump's own COP figures (diagnostic) |

### aroTHERM plus: calculated by this integration
| Entity | How it's calculated |
|---|---|
| `sensor.arotherm_plus_cop_live` | Heat output ÷ electrical input. Only while the compressor runs and input is ≥ 100 W; otherwise *unknown*. |
| `sensor.arotherm_plus_cop_15_min` | Energy-weighted COP over the last 15 minutes |
| `sensor.arotherm_plus_cop_today`, `_cop_this_month` | Heat pump heat counter ÷ integrated electricity. Attribute `partial_day` / `partial_month` is true until a full period has been tracked. |
| `sensor.arotherm_plus_electricity_used` | **Use this one in the Energy dashboard.** Integrated from the W reading, kept across restarts. |
| `sensor.arotherm_plus_electricity_used_today`, `_this_month` | Same, per day and per month |
| `sensor.arotherm_plus_compressor_starts_today`, `_this_month`, `_last_hour` | From the starts counter |
| `sensor.arotherm_plus_compressor_run_time_today`, `_average_run_length_today`, `_last_run_length` | From the running state |

### aroTHERM plus: binary sensors
| Entity | On when |
|---|---|
| `binary_sensor.arotherm_plus_compressor_running` | The heat pump's status code says "Compressor active" or "Deicing active". If the status isn't available, modulation **and** speed must both be above 0, with `State00` as the last resort. |
| `binary_sensor.arotherm_plus_defrost_active` | Defrost flag / "Defrosting" / "Deicing active" |
| `binary_sensor.arotherm_plus_heating_pump` | Pump state from `State01` |
| `binary_sensor.arotherm_plus_fault` | Any active error on the heat pump or controller |
| `binary_sensor.arotherm_plus_low_water_pressure` | Water pressure below the threshold set in options (default 1.0 bar) |
| `binary_sensor.arotherm_plus_short_cycling` | ≥ 3 starts in 60 min, or the last run was under 10 min. Both thresholds are set in options. |

### aroTHERM plus: diagnostic
- Refrigerant high and low pressure.
- Compressor inlet and outlet temperature, evaporation and condensation temperature.
- Air inlet temperature, EEV outlet temperature and fan speed.
- `sensor.heating_arotherm_plus_supply_temperature` and `sensor.heating_arotherm_plus_four_way_valve_hours`.
- `sensor.heating_arotherm_plus_high_pressure_switch`, `…_compressor_outlet_temperature_switch` and `…_electric_heater_temperature_switch` (open/closed).
- `sensor.heating_arotherm_plus_energy_integral_start_threshold`: −100 °min. This is an installer parameter that controls how often the compressor starts, so it is **deliberately read-only**.

### sensoCOMFORT VRC 720
| Entity | What it is |
|---|---|
| `climate.sensocomfort_vrc_720_zone_1` | Room temperature, setpoint and mode (OFF / AUTO / HEAT) |
| `sensor.sensocomfort_vrc_720_room_temperature`, `_room_setpoint` | Zone 1 room temperature and setpoint |
| `sensor.sensocomfort_vrc_720_heating_circuit_flow_target` | Flow target the controller has calculated |
| `sensor.sensocomfort_vrc_720_controller_clock_drift` | Controller clock minus HA clock, in minutes, from the controller's time broadcast. The time is in the attributes. |
| `sensor.sensocomfort_vrc_720_controller_active_errors` | Number of active controller errors |
| `sensor.heating_sensocomfort_vrc_720_average_outside_temperature` | Averaged outside temperature (the controller updates it every 3 h) |
| `sensor.heating_sensocomfort_vrc_720_heating_circuit_status` | `Hc1Status` as a raw number (1 while heating). ebusd's definition gives no meaning for the values. |
| `sensor.heating_sensocomfort_vrc_720_heating_curve_adaption` | Adaption applied by the adaptive curve. Read-only on purpose. |
| `sensor.heating_sensocomfort_vrc_720_controller_electricity_this_month`, `_last_month` | The controller's own electricity tally, kWh |

### ebusd
| Entity | What it is |
|---|---|
| `binary_sensor.ebusd_ebusd_connected` | ebusd reachable. Stays available when ebusd is down. |
| `binary_sensor.ebusd_ebus_signal` | Adapter has eBUS signal |
| `sensor.ebusd_ebus_signal_drops_today` | Signal dropouts counted today |
| `sensor.ebusd_bus_reads_per_minute`, `sensor.ebusd_bus_symbol_rate` | Bus load |

### Hot water (DHW): optional, off by default

For systems where the heat pump also heats a hot water cylinder. Turn on **Hot water (DHW) installed** in the options. With it off, none of these entities exist and none of these messages are read.

Entity IDs below are what HA would normally generate. Yours may get an area prefix (e.g. `heating_`).

| Entity | What it is | Source |
|---|---|---|
| `water_heater.sensocomfort_vrc_720_hot_water` | **Hot water**: current temperature, target (35–65 °C) and mode (off / auto / day / night) | `HwcStorageTemp` (or `HwcTemp`), `HwcTempDesired`, `HwcOpMode` |
| `sensor.sensocomfort_vrc_720_hot_water_cylinder_temperature` | Cylinder temperature (top/bottom variants exist, disabled by default) | `basv HwcStorageTemp(Top/Bottom)` |
| `sensor.arotherm_plus_hot_water_sensor_temperature` | Heat pump's own DHW sensor | `hmu HwcTemp` |
| `sensor.arotherm_plus_requested_hot_water_temperature` | Hot water temperature the controller is asking for | `hmu SetMode` (passive) |
| `sensor.arotherm_plus_hot_water_heat_produced_lifetime` / `_today` / `_this_month` | Hot water heat, kWh | `hmu YieldHwc…` |
| `binary_sensor.arotherm_plus_hot_water_charging` | Heat pump is heating the cylinder (status "Warm Water: … active") | `hmu Statuscode` |
| `binary_sensor.arotherm_plus_hot_water_mode_active` | Heat pump in hot water mode | `hmu HwcModeActive` |
| Diagnostic | Hot water flow target and maximum flow temperature, heat pump hot water target, hot water COP figures, hot water hours, compressor hot water run time and cycles, the controller's hot water electricity tally | |

When hot water is on, ***COP today / this month* include hot water heat as well as heating**, because the electricity figure covers both.

## Writable settings

All of these are *configuration* entities, so they stay off auto-generated dashboards.

| Entity | Setting | Allowed |
|---|---|---|
| `number.heating_sensocomfort_vrc_720_summer_temperature_limit` | Summer temperature limit (`Hc1SummerTempLimit`) | 10–25 °C, steps of 1 |
| `select.heating_sensocomfort_vrc_720_setback_mode` | Setback mode (`Hc1AutoOffMode`) | Eco (heating off during setback) / Night (reduced temperature) |
| `switch.heating_sensocomfort_vrc_720_adaptive_heating_curve` | Adaptive heating curve (`AdaptHeatCurve`) | on / off |
| `number.heating_sensocomfort_vrc_720_holiday_temperature` | Holiday temperature (`z1HolidayTemp`) | 5–25 °C, steps of 0.5 |
| `number.sensocomfort_vrc_720_night_setback_temperature` | Night (setback) temperature (`z1NightTemp`) | 10–22 °C, steps of 0.5 |
| `number.sensocomfort_vrc_720_quick_veto_temperature` | Quick veto temperature (`z1QuickVetoTemp`) | 12–25 °C, steps of 0.5 |
| `number.sensocomfort_vrc_720_heating_curve` | Heating curve (`Hc1HeatCurve`) | 0.2–1.5, steps of 0.05, at most ±0.2 per change |
| `number.sensocomfort_vrc_720_minimum_flow_temperature` | `Hc1MinFlowTempDesired` | 15–30 °C, at most ±5 K per change |
| `number.sensocomfort_vrc_720_maximum_flow_temperature` | `Hc1MaxFlowTempDesired` | 30–55 °C, at most ±5 K per change |
| `select.sensocomfort_vrc_720_zone_mode` | Zone mode (`z1OpMode`) | off / auto / day / night |
| `select.sensocomfort_vrc_720_zone_special_function` | Special function (`z1SFMode`) | none / party / quick veto / one day away / one day at home |
| `select.sensocomfort_vrc_720_room_temperature_modulation` | `Hc1RoomTempSwitchOn` | off / modulating / thermostat |
| *Hot water target temperature* / `water_heater…hot_water` target (DHW only) | `HwcTempDesired` | 35–65 °C, steps of 1, at most ±10 K per change |
| *Hot water mode* / `water_heater…hot_water` mode (DHW only) | `HwcOpMode` | off / auto / day / night |
| *Hot water special function* (DHW only) | `HwcSFMode` | None / One-off cylinder charge (`load`) |
| *Heat pump hot water mode* (DHW only) | `hmu HwcMode` | eco / normal / balance |
| `climate.sensocomfort_vrc_720_zone_1` | Mode: writes `z1OpMode`. Temperature: in AUTO, writes quick veto (`z1QuickVetoTemp`, then `z1SFMode = veto`). Refused in day mode. | |

**Never exposed:** energy counters (`YieldTotal`, `PrEnergySum…`), `EnergyIntegralStartHeating`, timers, holiday dates and installer settings. For hot water that includes cylinder charge hysteresis/offset, lock time, maximum charge time, parallel loading and maximum flow temperature.

### How every write is protected
1. **Off by default.** The integration options have *Allow writing settings* and *Dry run*.
2. **Dry run.** Nothing is sent. A notification and a logbook line show the exact command and the current and requested values.
3. **Limits.** Out-of-range values, wrong steps and options that aren't listed are refused. So are changes bigger than the per-change limit.
4. **Exactly one command.** The current value is read from the controller first, then one `write` is sent, never retried.
5. **Checked.** The value is read back from the controller, and an error is raised if it didn't stick.
6. **Recorded.** Each write appears in the logbook against the entity, and the last 20 are in diagnostics.
7. **Rate-limited.** At most one write every 5 s.
8. **Nothing writes on its own.** A write happens only when you change an entity, or when an automation you built does.

**Quick veto from the climate entity is experimental.** How the VRC 720 handles a veto started over eBUS (how long it lasts, how it ends) hasn't been verified yet. Try it in dry run first.

## Options

*Settings → Devices & services → aroTHERM ebusd → **Configure*** (not *Reconfigure*, which only changes host and ports). The two write switches are at the bottom.

| Option | Default |
|---|---|
| Power readings / Flow-return / Compressor state / Slow values / Counters-and-settings intervals | 15 / 30 / 60 / 300 / 3600 s |
| Short cycling: starts per hour / minimum run length | 3 / 10 min |
| Low water pressure alarm below | 1.0 bar |
| Allow writing settings | off |
| Dry run | on |
| Hot water (DHW) installed | off |

**Plausibility checks (0.2.2).** The bus occasionally delivers corrupted values, so every reading is checked before it's used:
- **Range checks.** For example: modulation 0–100 %, water temperatures 0–80 °C, air −40–60 °C, water pressure 0–4 bar, electrical input 0–6000 W, heat output 0–20 kW, COP 0–10. A reading outside its range is rejected and the previous value is kept.
- **Lifetime counters** (compressor/pump/fan starts and hours, heat produced, electricity used) may not go down or jump by more than a set step between reads. A reading that would is held back, and accepted only if the next read confirms it.
- **Where to see it.** Diagnostics show `rejected_count` and `last_rejected` for every message. With debug logging on, each rejection is logged.

**How polling works:**
- Values are read with `read -m <maxage>`, so ebusd answers from its cache when the value is fresh enough.
- `SetMode`, `State00/01/07`, `StatusCirPump`, outside temperature and the controller clock come free from the controller's own bus traffic, via ebusd's HTTP cache.
- About 15–20 bus reads a minute in total.

## Install / upgrade

The full steps, including backups, are in **INSTALL.md**.

To upgrade:
1. Replace `<HA_CONFIG>/custom_components/arotherm_ebusd/` with the folder from the new zip (currently `arotherm_ebusd-0.3.0.zip`).
2. Restart HA.

The entities, options and the integration's saved electricity totals carry over.

## Troubleshooting

| Symptom | Check |
|---|---|
| "Cannot connect to ebusd" during setup | ebusd's host is **192.168.1.22**, not the adapter (.25). Test with `Test-NetConnection 192.168.1.22 -Port 8888`. |
| "The HTTP/JSON port did not answer" | ebusd needs `--httpport=8889`, plus `8889:8889` in the compose `ports:`. Or set the HTTP port to 0 to use TCP only. |
| Everything unavailable | *ebusd connected* is off. It recovers on its own, with one error line and one "recovered" line in the log. |
| Bus values unavailable, ebusd connected on | The signal has been lost for more than 2 minutes. Shorter dropouts are only counted. |
| One value unavailable | Download diagnostics and look at `messages.<circuit>.<name>.last_error`. |
| COP shows *unknown* | Normal while the compressor is off or below 100 W. |
| A write raised "read back …" | The controller didn't accept the value. Nothing else was changed. |
| Options form shows `writes_enabled` instead of a label | Restart HA to reload the translations. |

**Diagnostics:** *Settings → Devices & services → aroTHERM ebusd → ⋮ → Download diagnostics*. It includes ebusd info and state, every message's value, age and last error, derived state, bus reads per minute and the write log.

**Debug logging:**
```yaml
logger:
  logs:
    custom_components.arotherm_ebusd: debug
```

## Known issues

- **Hot water support is untested on real hardware.** This system has no cylinder: the cylinder sensor answers `empty` and the heat pump's sensor −99. Message names and value lists come from ebusd's definitions, and the tests use synthetic values.

  On a system with a cylinder:
  - Check the values against the controller first.
  - Try every hot water setting in **dry run** before writing for real.
  - The meaning of *One-off cylinder charge* (`HwcSFMode = load`) is taken from the value name only.

- **The eBUS signal drops out often.** About 10 times an hour, for 15–60 s each time; ebusd's own `signal` topic shows the same, so it isn't caused by this integration. 0.2.1 keeps values available through dropouts shorter than 2 minutes.

  Things to check on your side: the adapter firmware update (1.1[6911] installed, 1[6a1a] available), the adapter's network link, its power supply and the eBUS wiring.
- **The bus sometimes delivers corrupted values around these dropouts.** Seen on 28 Oct, and ebusd's own MQTT entities show the same corrupt values:
  - *Compressor modulation* **142.06 %** at 14:55:32, with speed 0 and 16 W input.
  - *Compressor starts* **2273** instead of 6027 at 14:57:56.

  **Fixed in 0.2.2.** Both are now rejected; the tests replay these exact readings.

  **Left over from 0.2.1, which was running when they happened:**
  - *Compressor starts today / this month* restarted from 0 at 14:58 on 28 Oct. Today's count corrects itself at midnight; this month's count stays low until 1 Nov.
  - The false 1.7-minute run is stored as *Last run length*. *Short cycling* clears itself an hour after that run.
  - The long-term statistics of `sensor.arotherm_plus_compressor_starts_lifetime` (and the old `sensor.ebusd_hmu_compressorstarts`) recorded the dip to 2273 as a meter reset. You can correct that under *Developer tools → Statistics → Adjust sum*.
- **Partial first day and month.** *COP today / this month* and *electricity today / this month* only count from install (09:24 on 28 Oct). *Heat produced today* comes from the heat pump and counts from midnight, so today's COP is overstated. The `partial_day` attribute flags this until midnight.
- **Day temperature:** `z1DayTemp` answers `ERR: invalid position in decode` on this controller with the current definitions, so it isn't offered. The leftover `number.sensocomfort_vrc_720_day_temperature` from 0.1.0 can be deleted.
- **Heating circuit status** is shown as a raw number; its meaning isn't defined by ebusd.
- **Error codes** are the raw numbers ebusd reports. Whether they map one-to-one to F.xxx codes isn't verified.
- **Upgrading definitions:** if you upgrade ebusd's message definitions, some names may change. Check diagnostics afterwards.

## Changelog

See **CHANGELOG.md**. In short:
- **0.1.0:** first release.
- **0.2.0:** summer limit, setback mode, adaptive curve and holiday temperature; read-only controller and safety values; logbook entries for writes.
- **0.2.1:** 2-minute signal grace period; day temperature removed; deprecated device link removed.
- **0.2.2:** plausibility checks against corrupted bus values; stricter compressor-running rule.
- **0.3.0:** optional hot water (DHW) support.
