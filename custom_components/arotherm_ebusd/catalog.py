"""Catalogue of the ebusd messages this integration uses.

Every circuit/message name below was taken from the ebusd message
definitions reported by the user's own ebusd 26.1 (capture of 2026-10-27,
config files ebusd-2.1.x/en: vaillant/08.hmu.csv, 15.basv.csv, broadcast.csv).
Nothing here is invented: if a name is not in that capture, it is not here.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Added Hc1SummerTempLimit, Hc1AutoOffMode, AdaptHeatCurve, z1HolidayTemp (writable) and read-only Hc1Status, OutsideTempAvg, Hc1HeatCurveAdaption, EnergyIntegralStartHeating, safety switches, FourPortValveHours, SupplyTemp, PrEnergySumHcThis/LastMonth.
  0.2.1 (2026-10-28) - Removed z1DayTemp: it does not decode on this VRC 720 (ERR: invalid position in decode).
  0.2.2 (2026-10-28) - Plausibility ranges (PLAUSIBLE) and lifetime counter rules (COUNTERS) against corrupted bus values.
  0.3.0 (2026-10-28) - Optional hot water (DHW) messages (dhw=True), their value lists, plausibility ranges and write limits.
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import (
    TIER_FAST,
    TIER_FLOW,
    TIER_HOURLY,
    TIER_MEDIUM,
    TIER_PASSIVE,
    TIER_SLOW,
)


@dataclass(frozen=True, slots=True)
class Msg:
    """One ebusd message we read."""

    circuit: str
    name: str
    tier: str
    dhw: bool = False   # only polled when "Hot water (DHW) installed" is on

    @property
    def key(self) -> str:
        """Return the circuit.name key."""
        return f"{self.circuit}.{self.name}"


MESSAGES: tuple[Msg, ...] = (
    # --- fast (15 s): instantaneous power ---------------------------------
    Msg("hmu", "CurrentYieldPower", TIER_FAST),          # kW, D1B
    Msg("hmu", "CurrentConsumedPowerWatt", TIER_FAST),   # W, EXP (HP's own reading)
    # --- flow (30 s): hydraulics ------------------------------------------
    Msg("hmu", "FlowTemp", TIER_FLOW),                   # °C, D2C
    Msg("hmu", "ReturnTemp", TIER_FLOW),                 # °C, SIN/10
    Msg("hmu", "WaterThroughput", TIER_FLOW),            # l/h
    # --- medium (60 s): compressor state ----------------------------------
    Msg("hmu", "CompressorModulation", TIER_MEDIUM),     # %
    Msg("hmu", "CompressorSpeed", TIER_MEDIUM),          # rps
    Msg("hmu", "EnergyIntegral", TIER_MEDIUM),           # °min
    Msg("hmu", "Statuscode", TIER_MEDIUM),               # enum
    # --- slow (5 min) -----------------------------------------------------
    Msg("hmu", "AirIntakeTemp", TIER_SLOW),
    Msg("hmu", "HighPressure", TIER_SLOW),               # bar (refrigerant)
    Msg("hmu", "LowPressure", TIER_SLOW),                # bar (refrigerant)
    Msg("hmu", "CompressorOutletTemp", TIER_SLOW),
    Msg("hmu", "CompressorInletTemp", TIER_SLOW),
    Msg("hmu", "EvaporationTemp", TIER_SLOW),
    Msg("hmu", "CondensationTemp", TIER_SLOW),
    Msg("hmu", "AirInletTemp", TIER_SLOW),
    Msg("hmu", "EEVOutletTemp", TIER_SLOW),
    Msg("hmu", "RunDataFan1Speed", TIER_SLOW),           # rpm
    Msg("hmu", "FlowPressure", TIER_SLOW),               # bar (water)
    Msg("hmu", "BuildingCircuitPumpPower", TIER_SLOW),   # %
    Msg("hmu", "YieldHcDay", TIER_SLOW),                 # kWh
    Msg("hmu", "CompressorStarts", TIER_SLOW),           # counter
    Msg("hmu", "currenterror", TIER_SLOW),
    Msg("basv", "z1RoomTemp", TIER_SLOW),
    Msg("basv", "z1ActualRoomTempDesired", TIER_SLOW),
    Msg("basv", "Hc1ActualFlowTempDesired", TIER_SLOW),
    Msg("basv", "z1OpMode", TIER_SLOW),
    Msg("basv", "z1SFMode", TIER_SLOW),
    Msg("basv", "currenterror", TIER_SLOW),
    Msg("basv", "Hc1Status", TIER_SLOW),
    Msg("hmu", "SupplyTemp", TIER_SLOW),
    Msg("hmu", "TemperatureSwitchCompressorOutlet", TIER_SLOW),
    Msg("hmu", "HighPressureSwitch", TIER_SLOW),
    Msg("hmu", "TemperatureSwitchElectricHeater", TIER_SLOW),
    # --- hourly -----------------------------------------------------------
    Msg("hmu", "YieldHc", TIER_HOURLY),                  # kWh lifetime heat
    Msg("hmu", "YieldHcMonth", TIER_HOURLY),
    Msg("hmu", "TotalEnergyUsage", TIER_HOURLY),         # kWh lifetime electricity
    Msg("hmu", "CopHc", TIER_HOURLY),
    Msg("hmu", "CopHcMonth", TIER_HOURLY),
    Msg("hmu", "CompressorHours", TIER_HOURLY),
    Msg("hmu", "BuildingPumpHours", TIER_HOURLY),
    Msg("hmu", "BuildingPumpStarts", TIER_HOURLY),
    Msg("hmu", "Fan1Hours", TIER_HOURLY),
    Msg("hmu", "Fan1Starts", TIER_HOURLY),
    Msg("hmu", "TotalHours", TIER_HOURLY),
    Msg("basv", "z1QuickVetoTemp", TIER_HOURLY),
    Msg("basv", "z1NightTemp", TIER_HOURLY),
    Msg("basv", "Hc1HeatCurve", TIER_HOURLY),
    Msg("basv", "Hc1MinFlowTempDesired", TIER_HOURLY),
    Msg("basv", "Hc1MaxFlowTempDesired", TIER_HOURLY),
    Msg("basv", "Hc1RoomTempSwitchOn", TIER_HOURLY),
    Msg("basv", "Hc1SummerTempLimit", TIER_HOURLY),
    Msg("basv", "Hc1AutoOffMode", TIER_HOURLY),
    Msg("basv", "AdaptHeatCurve", TIER_HOURLY),
    Msg("basv", "z1HolidayTemp", TIER_HOURLY),
    Msg("basv", "Hc1HeatCurveAdaption", TIER_HOURLY),     # read-only: controller computes it
    Msg("basv", "OutsideTempAvg", TIER_HOURLY),           # controller updates it every 3 h
    Msg("basv", "PrEnergySumHcThisMonth", TIER_HOURLY),
    Msg("basv", "PrEnergySumHcLastMonth", TIER_HOURLY),
    Msg("hmu", "EnergyIntegralStartHeating", TIER_HOURLY),  # read-only: installer parameter
    Msg("hmu", "FourPortValveHours", TIER_HOURLY),
    # --- passive: refreshed by VRC 720 / VWZIO traffic, read from cache ----
    Msg("hmu", "SetMode", TIER_PASSIVE),
    Msg("hmu", "State00", TIER_PASSIVE),
    Msg("hmu", "State01", TIER_PASSIVE),
    Msg("hmu", "State07", TIER_PASSIVE),
    Msg("hmu", "StatusCirPump", TIER_PASSIVE),
    Msg("broadcast", "OutsideTemp", TIER_PASSIVE),
    Msg("broadcast", "vdatetime", TIER_PASSIVE),         # VRC 720 clock broadcast
    # --- hot water (DHW): only when the option is on (0.3.0) ---------------
    # Names/types from the same ebusd capture. NOT verified with live values:
    # the user's system has no cylinder (HwcStorageTemp 'empty', HwcTemp -99).
    Msg("basv", "HwcStorageTemp", TIER_SLOW, dhw=True),        # cylinder temp
    Msg("basv", "HwcStorageTempTop", TIER_SLOW, dhw=True),
    Msg("basv", "HwcStorageTempBottom", TIER_SLOW, dhw=True),
    Msg("hmu", "HwcTemp", TIER_SLOW, dhw=True),                # HP's DHW sensor
    Msg("basv", "HwcTempDesired", TIER_SLOW, dhw=True),        # writable
    Msg("basv", "HwcOpMode", TIER_SLOW, dhw=True),             # writable
    Msg("basv", "HwcSFMode", TIER_SLOW, dhw=True),             # writable (auto/load)
    Msg("hmu", "HwcModeActive", TIER_SLOW, dhw=True),
    Msg("hmu", "YieldHwcDay", TIER_SLOW, dhw=True),
    Msg("hmu", "HwcMode", TIER_HOURLY, dhw=True),              # writable eco/normal/balance
    Msg("basv", "HwcFlowTemp", TIER_HOURLY, dhw=True),
    Msg("basv", "HwcMaxFlowTempDesired", TIER_HOURLY, dhw=True),
    Msg("hmu", "TargetTempHwc", TIER_HOURLY, dhw=True),
    Msg("hmu", "YieldHwc", TIER_HOURLY, dhw=True),
    Msg("hmu", "YieldHwcMonth", TIER_HOURLY, dhw=True),
    Msg("hmu", "CopHwc", TIER_HOURLY, dhw=True),
    Msg("hmu", "CopHwcMonth", TIER_HOURLY, dhw=True),
    Msg("hmu", "HwcHours", TIER_HOURLY, dhw=True),
    Msg("hmu", "RunStatsCompressorHwc", TIER_HOURLY, dhw=True),  # runtime min, cycles
    Msg("basv", "PrEnergySumHwc", TIER_HOURLY, dhw=True),
    Msg("basv", "PrEnergySumHwcThisMonth", TIER_HOURLY, dhw=True),
    Msg("basv", "PrEnergySumHwcLastMonth", TIER_HOURLY, dhw=True),
)

MESSAGES_BY_KEY: dict[str, Msg] = {m.key: m for m in MESSAGES}

# --- field positions (non-ignored fields, in definition order) -------------
# hmu SetMode: hcmode, flowtempdesired, hwctempdesired, hwcflowtempdesired,
#              disablehc, disablehwctapping, disablehwcload, ...
SETMODE_FLOWTEMPDESIRED = 1
SETMODE_DISABLEHC = 4
# hmu State00: S00_SupplyTemp, field2, S00_CompressorModulation,
#              CompressorState, HeatingState, field6, Defrost, S00_CompressorPower
STATE00_COMPRESSORSTATE = 3
STATE00_DEFROST = 6
# hmu State01: temp1(flow), temp1(return), temp2, temp1, temp1, pumpstate
STATE01_PUMPSTATE = 5
# hmu State07: power, energy (daily environmental energy yield, kWh), ...
STATE07_ENERGY = 1
# broadcast vdatetime: time (HH:MM:SS), date (DD.MM.YYYY)
VDATETIME_TIME = 0
VDATETIME_DATE = 1

# --- enum value lists, exactly as defined in the user's ebusd CSVs ---------
STATUSCODE_OPTIONS: tuple[str, ...] = (
    "Frost protection", "Standby", "Heating: Compressor shutdown",
    "Heating: Compressor blocked", "Heating: Prerun", "Heating: Compressor active",
    "Heating: Overrun", "Cooling: Compressor shutdown", "Cooling: Compressor blocked",
    "Cooling: Prerun", "Cooling: Compressor active", "Cooling: Overrun",
    "Heating: Immersion heater active", "Warm Water: Compressor blocked",
    "Warm Water: Prerun", "Warm Water: Compressor active",
    "Warm Water: Immersion Heater active", "Warm Water: Overrun",
    "Heating: Immersion Heater shutdown", "Heating: Immersion Heater blocked",
    "Warm Water: Immersion Heater shutdown", "Warm Water: Immersion Heater blocked",
    "Air purging program active", "Compressor oil heating activated",
    "Fan 1 blocked", "Fan 1 air inlet too high", "Fan 1 air inlet too low",
    "Fan 2 blocked", "Building circuit flow too low", "Building circuit pump fault",
    "Frequency converter fault: Compressor", "Frequency converter fault: Mains voltage",
    "Frequency converter fault: Overheating", "Deicing time too long",
    "Deicing flow temperature too low", "Compressor outlet temperature too high",
    "Hot gas temperature switch open", "Fan 1: Wind", "Fan 2: Wind",
    "Current limt active", "High pressure switch open",
    "Evaporation temperature too low", "Condensation temperature too low",
    "Evaporation temperature too high", "Condensation temperature too high",
    "Building circuit return temperature too low",
    "Building circuit return temperature too high",
    "Immersion heater: Flow temperature too high", "Deicing active",
    "Frequency converter fault", "Connection fault: frequency converter",
    "4-port-valve position fault",
)
STATUS_RUNNING = ("Compressor active", "Deicing active")
STATE00_RUNNING = ("Heating", "Defrosting")

Z1_OPMODE_OPTIONS: tuple[str, ...] = ("off", "auto", "day", "night")
# ventilation/load from the definition are irrelevant for this system and omitted
Z1_SFMODE_OPTIONS: tuple[str, ...] = (
    "auto", "party", "veto", "onedayaway", "onedayathome",
)
HC1_RCMODE_OPTIONS: tuple[str, ...] = ("off", "modulating", "thermostat")
HC1_OFFMODE_OPTIONS: tuple[str, ...] = ("eco", "night")
HWC_OPMODE_OPTIONS: tuple[str, ...] = ("off", "auto", "day", "night")
# HwcSFMode: only "auto" (normal) and "load" (one-off cylinder charge) are offered
HWC_SFMODE_OPTIONS: tuple[str, ...] = ("auto", "load")
HMU_HWCMODE_OPTIONS: tuple[str, ...] = ("eco", "normal", "balance")
SETMODE_HWCTEMPDESIRED = 2
SETMODE_DISABLEHWCLOAD = 6
RUNSTATS_HWC_RUNTIME = 0
RUNSTATS_HWC_CYCLES = 1
YESNO_OPTIONS: tuple[str, ...] = ("no", "yes")
SWITCH_STATE_OPTIONS: tuple[str, ...] = ("open", "closed")


# --- plausibility checks (0.2.2) --------------------------------------------
# The live bus occasionally delivers corrupted values around signal dropouts
# (seen 2026-10-28: CompressorModulation 142.06 %, CompressorStarts 2273
# instead of 6027; ebusd's own MQTT entities showed the same values).
# A value outside its range is rejected and the previous value is kept.
# Ranges are generous physical limits for this installation, not setpoints.
_WATER = (0.0, 80.0)
_AIR = (-40.0, 60.0)
_REFRIG = (-40.0, 140.0)
PLAUSIBLE: dict[str, dict[int, tuple[float, float]]] = {
    "hmu.CurrentYieldPower": {0: (0.0, 20.0)},
    "hmu.CurrentConsumedPowerWatt": {0: (0.0, 6000.0)},
    "hmu.FlowTemp": {0: _WATER},
    "hmu.ReturnTemp": {0: _WATER},
    "hmu.SupplyTemp": {0: _WATER},
    "hmu.WaterThroughput": {0: (0.0, 3000.0)},
    "hmu.CompressorModulation": {0: (0.0, 100.0)},
    "hmu.CompressorSpeed": {0: (0.0, 150.0)},
    "hmu.EnergyIntegral": {0: (-3000.0, 3000.0)},
    "hmu.EnergyIntegralStartHeating": {0: (-3000.0, 0.0)},
    "hmu.AirIntakeTemp": {0: _AIR},
    "hmu.AirInletTemp": {0: _AIR},
    "broadcast.OutsideTemp": {0: _AIR},
    "basv.OutsideTempAvg": {0: _AIR},
    "hmu.HighPressure": {0: (0.0, 50.0)},
    "hmu.LowPressure": {0: (0.0, 50.0)},
    "hmu.CompressorOutletTemp": {0: _REFRIG},
    "hmu.CompressorInletTemp": {0: _REFRIG},
    "hmu.EvaporationTemp": {0: _REFRIG},
    "hmu.CondensationTemp": {0: _REFRIG},
    "hmu.EEVOutletTemp": {0: _REFRIG},
    "hmu.FlowPressure": {0: (0.0, 4.0)},
    "hmu.BuildingCircuitPumpPower": {0: (0.0, 100.0)},
    "hmu.RunDataFan1Speed": {0: (0.0, 2000.0)},
    "hmu.YieldHcDay": {0: (0.0, 300.0)},
    "hmu.YieldHcMonth": {0: (0.0, 6000.0)},
    "hmu.CopHc": {0: (0.0, 10.0)},
    "hmu.CopHcMonth": {0: (0.0, 10.0)},
    "hmu.SetMode": {1: _WATER},                  # flowtempdesired
    "hmu.State00": {0: _WATER, 2: (0.0, 100.0)},  # supply temp, modulation
    "hmu.State07": {1: (0.0, 300.0)},             # environmental energy today
    "basv.z1RoomTemp": {0: (0.0, 40.0)},
    "basv.z1ActualRoomTempDesired": {0: (0.0, 35.0)},
    "basv.Hc1ActualFlowTempDesired": {0: _WATER},
    "basv.PrEnergySumHcThisMonth": {0: (0.0, 6000.0)},
    "basv.PrEnergySumHcLastMonth": {0: (0.0, 6000.0)},
    "basv.HwcStorageTemp": {0: (0.0, 95.0)},
    "basv.HwcStorageTempTop": {0: (0.0, 95.0)},
    "basv.HwcStorageTempBottom": {0: (0.0, 95.0)},
    "hmu.HwcTemp": {0: (0.0, 95.0)},
    "basv.HwcTempDesired": {0: (0.0, 80.0)},
    "basv.HwcFlowTemp": {0: (0.0, 95.0)},
    "hmu.TargetTempHwc": {0: (0.0, 95.0)},
    "hmu.YieldHwcDay": {0: (0.0, 300.0)},
    "hmu.YieldHwcMonth": {0: (0.0, 6000.0)},
    "hmu.CopHwc": {0: (0.0, 10.0)},
    "hmu.CopHwcMonth": {0: (0.0, 10.0)},
    "basv.PrEnergySumHwcThisMonth": {0: (0.0, 6000.0)},
    "basv.PrEnergySumHwcLastMonth": {0: (0.0, 6000.0)},
}

# Lifetime counters: must never go down, and may only rise by a plausible
# amount between two accepted reads. A reading that breaks this is held back
# and only accepted if the next read confirms it (same value +/- max step).
COUNTERS: dict[str, float] = {
    "hmu.CompressorStarts": 30,
    "hmu.BuildingPumpStarts": 30,
    "hmu.Fan1Starts": 30,
    "hmu.CompressorHours": 5,
    "hmu.BuildingPumpHours": 5,
    "hmu.Fan1Hours": 5,
    "hmu.TotalHours": 5,
    "hmu.FourPortValveHours": 5,
    "hmu.YieldHc": 100,
    "hmu.TotalEnergyUsage": 30,
    "hmu.YieldHwc": 100,
    "hmu.HwcHours": 5,
    "basv.PrEnergySumHwc": 30,
}


@dataclass(frozen=True, slots=True)
class WritableNumber:
    """Safety limits for a writable numeric value (our own limits, not ebusd's).

    ebusd's definitions give these messages no useful range (EXP float), so
    the limits below are conservative choices for this installation.
    """

    key: str
    min_value: float
    max_value: float
    step: float
    max_change: float | None = None  # largest change allowed in one write


WRITABLE_NUMBERS: dict[str, WritableNumber] = {
    "basv.z1QuickVetoTemp": WritableNumber("basv.z1QuickVetoTemp", 12, 25, 0.5),
    "basv.z1NightTemp": WritableNumber("basv.z1NightTemp", 10, 22, 0.5),
    "basv.Hc1HeatCurve": WritableNumber("basv.Hc1HeatCurve", 0.2, 1.5, 0.05, 0.2),
    "basv.Hc1MinFlowTempDesired": WritableNumber(
        "basv.Hc1MinFlowTempDesired", 15, 30, 1, 5
    ),
    "basv.Hc1MaxFlowTempDesired": WritableNumber(
        "basv.Hc1MaxFlowTempDesired", 30, 55, 1, 5
    ),
    "basv.Hc1SummerTempLimit": WritableNumber("basv.Hc1SummerTempLimit", 10, 25, 1),
    "basv.z1HolidayTemp": WritableNumber("basv.z1HolidayTemp", 5, 25, 0.5),
    # hot water target: 35-65 C, at most 10 K per change
    "basv.HwcTempDesired": WritableNumber("basv.HwcTempDesired", 35, 65, 1, 10),
}

WRITABLE_SELECTS: dict[str, tuple[str, ...]] = {
    "basv.z1OpMode": Z1_OPMODE_OPTIONS,
    "basv.z1SFMode": Z1_SFMODE_OPTIONS,
    "basv.Hc1RoomTempSwitchOn": HC1_RCMODE_OPTIONS,
    "basv.Hc1AutoOffMode": HC1_OFFMODE_OPTIONS,
    "basv.AdaptHeatCurve": YESNO_OPTIONS,           # exposed as a switch
    "basv.HwcOpMode": HWC_OPMODE_OPTIONS,
    "basv.HwcSFMode": HWC_SFMODE_OPTIONS,
    "hmu.HwcMode": HMU_HWCMODE_OPTIONS,
}
