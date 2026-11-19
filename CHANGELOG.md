<!--
arotherm_ebusd CHANGELOG - version 0.3.0 (2026-10-28)
-->

# Changelog

## 0.3.0 (2026-10-28) - optional hot water (DHW) support
For systems where the heat pump also heats a hot water cylinder.

- **New option *Hot water (DHW) installed*** (off by default). With it off, nothing changes: no hot water entities and no extra bus reads.
- **When it's on, you get:**
  - **Water heater entity *Hot water*:**
    - Current temperature: the cylinder sensor (`HwcStorageTemp`), or the heat pump's DHW sensor (`HwcTemp`) if that's missing.
    - Target temperature: `HwcTempDesired`, limited to 35–65 °C and at most 10 K per change.
    - Operation mode: `HwcOpMode` (off / auto / day / night).
  - **Settings:**
    - *Hot water mode* (`HwcOpMode`).
    - *Hot water special function*: `HwcSFMode`, offered as *None* or *One-off cylinder charge* (`load`) only.
    - *Heat pump hot water mode*: `HwcMode`, eco / normal / balance.
    - *Hot water target temperature*.
  - **Sensors:**
    - Cylinder temperature (the top and bottom sensors are disabled by default).
    - Heat pump DHW sensor temperature and requested hot water temperature.
    - Hot water flow target, hot water maximum flow temperature and heat pump hot water target.
    - Hot water heat produced: lifetime, today, this month.
    - The heat pump's hot water COP figures.
    - Hot water hours, compressor hot water run time and cycles.
    - The controller's hot water electricity tally.
  - **Binary sensors:** *Hot water charging* (from the status code) and *Hot water mode active*.
  - ***COP today / this month*** include hot water heat as well as heating, because the electricity figure covers both.
- All hot water writes use the same guards as everything else: off by default, dry run, limits, read-back check and logbook entry.
- **Not verified on live hardware.** The system this was developed on has no cylinder; its cylinder sensor answers `empty` and the heat pump's sensor −99. Message names and value lists come from ebusd's definitions, and the tests use synthetic values.

## 0.2.2 (2026-10-28) - plausibility checks
The live bus occasionally delivers corrupted values around its signal dropouts. ebusd's own MQTT entities show the same values. Two examples from 28 Oct:
- compressor modulation **142.06 %** (with speed 0 and 16 W input), which faked a 1.7-minute run and a *Short cycling* alarm;
- compressor starts **2273** instead of 6027, which reset *starts today / this month*.

Changes:
- **Every value is range-checked before use** (e.g. modulation 0–100 %, water temperatures 0–80 °C, water pressure 0–4 bar, power 0–6000 W, COP 0–10). An implausible reading is rejected and the previous value is kept. Diagnostics show `rejected_count` and `last_rejected` for each message.
- **Lifetime counters** (starts, hours, heat produced, electricity) can no longer go down or jump. A reading that would is held back. It is accepted only if the next read confirms it, so a genuine change still gets through about a minute later.
- **Compressor running** is now decided by the heat pump's status code. If that isn't available, modulation **and** speed must both be above zero. One corrupt value can no longer fake a run.

## 0.2.1 (2026-10-28) - fixes from the first live run
- Signal grace period. The live bus loses its signal about 10 times an hour for 15–60 s each time. Bus entities now stay available unless the signal has been gone for more than 2 minutes. Polling pauses while the signal is down, and every dropout is still counted in *eBUS signal drops today*.
- Removed the *Day temperature* number. `z1DayTemp` answers `ERR: invalid position in decode` on this VRC 720 with the ebusd-2.1.x definitions. The climate entity now refuses to set a temperature in day (manual) mode; quick veto in auto mode is unchanged.
- Removed the deprecated `via_device` device link, which HA 2026.10 warns about.

## 0.2.0 (2026-10-28)
- New writable settings (off until writes are enabled; dry run by default):
  - Summer temperature limit (`Hc1SummerTempLimit`): number, 10–25 °C, steps of 1.
  - Setback mode (`Hc1AutoOffMode`): select, eco / night only.
  - Adaptive heating curve (`AdaptHeatCurve`): switch.
  - Holiday temperature (`z1HolidayTemp`): number, 5–25 °C, steps of 0.5.
- New read-only values: heating circuit status (`Hc1Status`), average outside temperature, heating curve adaption, energy-integral start threshold (installer parameter, deliberately not writable), compressor outlet / high pressure / electric heater safety switches, four-way valve hours, supply temperature, and the controller's electricity this month / last month.
- Every write and dry run is now recorded in the logbook against the entity.

## 0.1.0 (2026-10-28)
- First release for ebusd 26.1 with ebusd-2.1.x definitions: HMU00 (08), BASV3 (15).
- UI config flow (host, TCP port, HTTP port), options flow (poll tiers, short-cycling, low pressure, write safety) and reconfigure.
- Tiered polling with `read -m <maxage>`. Passive values come from ebusd's HTTP cache, with TCP as fallback.
- Sensors, binary sensors, numbers, selects and a zone 1 climate entity.
- Derived values: live and 15-minute COP; COP today and this month; integrated electricity (total, day, month); compressor starts, run time and short cycling; eBUS signal drops; controller clock drift.
- Guarded writes: off by default, dry run, limits, max change per step, read-before/verify-after, rate limit, write log.
- Diagnostics download and English translations.
- JSON files (manifest, strings, translations) can't hold comments, so they carry `version` / `_version` and `_changelog` keys instead.
