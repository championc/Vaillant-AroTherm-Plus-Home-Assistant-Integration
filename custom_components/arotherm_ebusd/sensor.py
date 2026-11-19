"""Sensors for aroTHERM ebusd.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - New read-only sensors (controller status/averages/adaption, safety switches, valve hours, supply temp, energy-integral start threshold, controller monthly electricity).
  0.2.1 (2026-10-28) - Version bump only; no functional change.
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - Optional hot water sensors; COP today/month include hot water heat when DHW is on.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .catalog import (
    RUNSTATS_HWC_CYCLES,
    RUNSTATS_HWC_RUNTIME,
    SETMODE_FLOWTEMPDESIRED,
    SETMODE_HWCTEMPDESIRED,
    STATE07_ENERGY,
    STATUSCODE_OPTIONS,
    SWITCH_STATE_OPTIONS,
)
from .const import DEVICE_CONTROLLER, DEVICE_EBUSD, DEVICE_HEATPUMP
from .coordinator import ArothermConfigEntry, ArothermCoordinator
from .entity import ArothermEntity

TEMP = {"device_class": SensorDeviceClass.TEMPERATURE,
        "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
        "suggested_display_precision": 1}
KWH_TOTAL = {"device_class": SensorDeviceClass.ENERGY,
             "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
             "state_class": SensorStateClass.TOTAL_INCREASING}
BAR = {"device_class": SensorDeviceClass.PRESSURE,
       "native_unit_of_measurement": UnitOfPressure.BAR,
       "state_class": SensorStateClass.MEASUREMENT,
       "suggested_display_precision": 2}
HOURS_TOTAL = {"device_class": SensorDeviceClass.DURATION,
               "native_unit_of_measurement": UnitOfTime.HOURS,
               "state_class": SensorStateClass.TOTAL_INCREASING,
               "entity_category": EntityCategory.DIAGNOSTIC}
COP = {"state_class": SensorStateClass.MEASUREMENT, "suggested_display_precision": 2}
DIAG = {"entity_category": EntityCategory.DIAGNOSTIC}


@dataclass(frozen=True, kw_only=True)
class ArothermSensorDescription(SensorEntityDescription):
    """Sensor description."""

    device: str = DEVICE_HEATPUMP
    dhw: bool = False          # only created when hot water (DHW) is enabled
    msg: str | None = None
    field: int = 0
    bus: bool = True
    value_fn: Callable[[ArothermCoordinator], Any] | None = None
    attrs_fn: Callable[[ArothermCoordinator], dict[str, Any]] | None = None


def _d(key: str, msg: str | None = None, **kw: Any) -> ArothermSensorDescription:
    return ArothermSensorDescription(key=key, msg=msg, **kw)


def _delta_t(c: ArothermCoordinator) -> float | None:
    flow, ret = c.num("hmu.FlowTemp"), c.num("hmu.ReturnTemp")
    return round(flow - ret, 2) if flow is not None and ret is not None else None


def _status(c: ArothermCoordinator) -> str | None:
    v = c.field("hmu.Statuscode")
    return v if v in STATUSCODE_OPTIONS else None


def _error_count(circuit: str) -> Callable[[ArothermCoordinator], int | None]:
    def fn(c: ArothermCoordinator) -> int | None:
        errs = c.errors(circuit)
        return None if errs is None else len(errs)
    return fn


def _error_attrs(circuit: str) -> Callable[[ArothermCoordinator], dict[str, Any]]:
    return lambda c: {"error_codes": c.errors(circuit) or []}


def _minutes(seconds: float | None) -> float | None:
    return None if seconds is None else round(seconds / 60.0, 1)


SENSORS: tuple[ArothermSensorDescription, ...] = (
    # --- heat pump: hydraulics / temperatures
    _d("flow_temp", "hmu.FlowTemp", **TEMP),
    _d("return_temp", "hmu.ReturnTemp", **TEMP),
    _d("flow_return_delta", None, value_fn=_delta_t, native_unit_of_measurement="K",
       state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1),
    _d("flow_temp_desired", "hmu.SetMode", field=SETMODE_FLOWTEMPDESIRED, **TEMP),
    _d("water_flow", "hmu.WaterThroughput", device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
       native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
       state_class=SensorStateClass.MEASUREMENT),
    _d("system_pressure", "hmu.FlowPressure", **BAR),
    _d("air_intake_temp", "hmu.AirIntakeTemp", **TEMP),
    _d("outside_temp", "broadcast.OutsideTemp", **TEMP),
    _d("pump_power", "hmu.BuildingCircuitPumpPower", native_unit_of_measurement=PERCENTAGE,
       state_class=SensorStateClass.MEASUREMENT),
    # --- heat pump: power & compressor
    _d("heat_output", "hmu.CurrentYieldPower", device_class=SensorDeviceClass.POWER,
       native_unit_of_measurement=UnitOfPower.KILO_WATT, state_class=SensorStateClass.MEASUREMENT,
       suggested_display_precision=1),
    _d("electric_power", "hmu.CurrentConsumedPowerWatt", device_class=SensorDeviceClass.POWER,
       native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT,
       suggested_display_precision=0),
    _d("compressor_modulation", "hmu.CompressorModulation", native_unit_of_measurement=PERCENTAGE,
       state_class=SensorStateClass.MEASUREMENT),
    _d("compressor_speed", "hmu.CompressorSpeed", native_unit_of_measurement="rps",
       state_class=SensorStateClass.MEASUREMENT),
    _d("energy_integral", "hmu.EnergyIntegral", native_unit_of_measurement="°min",
       state_class=SensorStateClass.MEASUREMENT),
    _d("status", "hmu.Statuscode", value_fn=_status, device_class=SensorDeviceClass.ENUM,
       options=list(STATUSCODE_OPTIONS)),
    _d("hp_errors", "hmu.currenterror", value_fn=_error_count("hmu"),
       attrs_fn=_error_attrs("hmu"), state_class=SensorStateClass.MEASUREMENT),
    # --- heat pump: refrigerant circuit (diagnostic)
    _d("high_pressure", "hmu.HighPressure", **{**BAR, **DIAG}),
    _d("low_pressure", "hmu.LowPressure", **{**BAR, **DIAG}),
    _d("compressor_outlet_temp", "hmu.CompressorOutletTemp", **{**TEMP, **DIAG}),
    _d("compressor_inlet_temp", "hmu.CompressorInletTemp", **{**TEMP, **DIAG}),
    _d("evaporation_temp", "hmu.EvaporationTemp", **{**TEMP, **DIAG}),
    _d("condensation_temp", "hmu.CondensationTemp", **{**TEMP, **DIAG}),
    _d("air_inlet_temp", "hmu.AirInletTemp", **{**TEMP, **DIAG}),
    _d("supply_temp", "hmu.SupplyTemp", **{**TEMP, **DIAG}),
    _d("energy_integral_start", "hmu.EnergyIntegralStartHeating", native_unit_of_measurement="°min",
       **DIAG),
    _d("four_port_valve_hours", "hmu.FourPortValveHours", **HOURS_TOTAL),
    _d("switch_compressor_outlet", "hmu.TemperatureSwitchCompressorOutlet",
       device_class=SensorDeviceClass.ENUM, options=list(SWITCH_STATE_OPTIONS), **DIAG),
    _d("switch_high_pressure", "hmu.HighPressureSwitch",
       device_class=SensorDeviceClass.ENUM, options=list(SWITCH_STATE_OPTIONS), **DIAG),
    _d("switch_electric_heater", "hmu.TemperatureSwitchElectricHeater",
       device_class=SensorDeviceClass.ENUM, options=list(SWITCH_STATE_OPTIONS), **DIAG),
    _d("eev_outlet_temp", "hmu.EEVOutletTemp", **{**TEMP, **DIAG}),
    _d("fan_speed", "hmu.RunDataFan1Speed", native_unit_of_measurement="rpm",
       state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0, **DIAG),
    # --- heat pump: energy counters reported by the HP
    _d("heat_yield_total", "hmu.YieldHc", **KWH_TOTAL),
    _d("heat_yield_today", "hmu.YieldHcDay", **KWH_TOTAL),
    _d("heat_yield_month", "hmu.YieldHcMonth", **KWH_TOTAL),
    _d("electric_energy_reported", "hmu.TotalEnergyUsage", **KWH_TOTAL),
    _d("environmental_energy_today", "hmu.State07", field=STATE07_ENERGY, **KWH_TOTAL),
    _d("cop_reported", "hmu.CopHc", **{**COP, **DIAG}),
    _d("cop_reported_month", "hmu.CopHcMonth", **{**COP, **DIAG}),
    _d("compressor_starts_total", "hmu.CompressorStarts",
       state_class=SensorStateClass.TOTAL_INCREASING),
    _d("compressor_hours", "hmu.CompressorHours", **HOURS_TOTAL),
    _d("pump_hours", "hmu.BuildingPumpHours", **HOURS_TOTAL),
    _d("pump_starts", "hmu.BuildingPumpStarts", state_class=SensorStateClass.TOTAL_INCREASING,
       entity_category=EntityCategory.DIAGNOSTIC),
    _d("fan_hours", "hmu.Fan1Hours", **HOURS_TOTAL),
    _d("fan_starts", "hmu.Fan1Starts", state_class=SensorStateClass.TOTAL_INCREASING,
       entity_category=EntityCategory.DIAGNOSTIC),
    _d("total_hours", "hmu.TotalHours", **HOURS_TOTAL),
    # --- derived (calculated in this integration)
    _d("cop_live", None, value_fn=lambda c: c.derived.cop_live(
        c.num("hmu.CurrentYieldPower"), c.num("hmu.CurrentConsumedPowerWatt"),
        c.compressor_running()), **COP),
    _d("cop_15min", None, value_fn=lambda c: c.derived.cop_window(), **COP),
    _d("cop_today", None, value_fn=lambda c: c.derived.cop_period(
        c.heat_today(), c.derived.elec_day_kwh), **COP,
       attrs_fn=lambda c: {"partial_day": c.derived.day_partial}),
    _d("cop_month", None, value_fn=lambda c: c.derived.cop_period(
        c.heat_month(), c.derived.elec_month_kwh), **COP,
       attrs_fn=lambda c: {"partial_month": c.derived.month_partial}),
    _d("electric_energy", None, value_fn=lambda c: round(c.derived.elec_total_kwh, 3),
       bus=False, suggested_display_precision=2, **KWH_TOTAL),
    _d("electric_energy_today", None, value_fn=lambda c: round(c.derived.elec_day_kwh, 3),
       bus=False, suggested_display_precision=2, **KWH_TOTAL,
       attrs_fn=lambda c: {"partial_day": c.derived.day_partial}),
    _d("electric_energy_month", None, value_fn=lambda c: round(c.derived.elec_month_kwh, 3),
       bus=False, suggested_display_precision=2, **KWH_TOTAL,
       attrs_fn=lambda c: {"partial_month": c.derived.month_partial}),
    _d("starts_today", None, value_fn=lambda c: c.derived.starts_today(),
       state_class=SensorStateClass.TOTAL_INCREASING),
    _d("starts_month", None, value_fn=lambda c: c.derived.starts_month(),
       state_class=SensorStateClass.TOTAL_INCREASING),
    _d("starts_last_hour", None, value_fn=lambda c: c.derived.starts_last_hour(time.time()),
       state_class=SensorStateClass.MEASUREMENT),
    _d("runtime_today", None, value_fn=lambda c: round(c.derived.runtime_day_s / 3600.0, 2),
       device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.HOURS,
       state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=2),
    _d("avg_run_today", None, value_fn=lambda c: _minutes(c.derived.avg_run_today_s()),
       device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES,
       state_class=SensorStateClass.MEASUREMENT),
    _d("last_run", None, value_fn=lambda c: _minutes(c.derived.last_run_s),
       device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES,
       state_class=SensorStateClass.MEASUREMENT),
    # --- controller
    _d("room_temp", "basv.z1RoomTemp", device=DEVICE_CONTROLLER, **TEMP),
    _d("room_setpoint", "basv.z1ActualRoomTempDesired", device=DEVICE_CONTROLLER, **TEMP),
    _d("flow_temp_target_hc1", "basv.Hc1ActualFlowTempDesired", device=DEVICE_CONTROLLER, **TEMP),
    _d("controller_clock_drift", "broadcast.vdatetime", device=DEVICE_CONTROLLER,
       value_fn=lambda c: c.controller_clock()[1], native_unit_of_measurement=UnitOfTime.MINUTES,
       state_class=SensorStateClass.MEASUREMENT,
       attrs_fn=lambda c: {"controller_time": c.controller_clock()[0]}),
    _d("outside_temp_avg", "basv.OutsideTempAvg", device=DEVICE_CONTROLLER, **TEMP),
    _d("hc1_status", "basv.Hc1Status", device=DEVICE_CONTROLLER, **DIAG),
    _d("heat_curve_adaption", "basv.Hc1HeatCurveAdaption", device=DEVICE_CONTROLLER,
       state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2, **DIAG),
    _d("controller_electricity_this_month", "basv.PrEnergySumHcThisMonth",
       device=DEVICE_CONTROLLER, **{**KWH_TOTAL, **DIAG}),
    _d("controller_electricity_last_month", "basv.PrEnergySumHcLastMonth",
       device=DEVICE_CONTROLLER, device_class=SensorDeviceClass.ENERGY,
       native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, **DIAG),
    _d("controller_errors", "basv.currenterror", device=DEVICE_CONTROLLER,
       value_fn=_error_count("basv"), attrs_fn=_error_attrs("basv"),
       state_class=SensorStateClass.MEASUREMENT),
    # --- ebusd
    # --- hot water (DHW): only when enabled in options
    _d("hw_cylinder_temp", "basv.HwcStorageTemp", device=DEVICE_CONTROLLER, dhw=True, **TEMP),
    _d("hw_cylinder_temp_top", "basv.HwcStorageTempTop", device=DEVICE_CONTROLLER, dhw=True,
       entity_registry_enabled_default=False, **TEMP),
    _d("hw_cylinder_temp_bottom", "basv.HwcStorageTempBottom", device=DEVICE_CONTROLLER, dhw=True,
       entity_registry_enabled_default=False, **TEMP),
    _d("hw_sensor_temp", "hmu.HwcTemp", dhw=True, **TEMP),
    _d("hw_requested_temp", "hmu.SetMode", field=SETMODE_HWCTEMPDESIRED, dhw=True, **TEMP),
    _d("hw_flow_temp", "basv.HwcFlowTemp", device=DEVICE_CONTROLLER, dhw=True, **TEMP),
    _d("hw_max_flow_temp", "basv.HwcMaxFlowTempDesired", device=DEVICE_CONTROLLER, dhw=True,
       **{**TEMP, **DIAG}),
    _d("hw_target_hp", "hmu.TargetTempHwc", dhw=True, **{**TEMP, **DIAG}),
    _d("hw_heat_total", "hmu.YieldHwc", dhw=True, **KWH_TOTAL),
    _d("hw_heat_today", "hmu.YieldHwcDay", dhw=True, **KWH_TOTAL),
    _d("hw_heat_month", "hmu.YieldHwcMonth", dhw=True, **KWH_TOTAL),
    _d("hw_cop_reported", "hmu.CopHwc", dhw=True, **{**COP, **DIAG}),
    _d("hw_cop_reported_month", "hmu.CopHwcMonth", dhw=True, **{**COP, **DIAG}),
    _d("hw_hours", "hmu.HwcHours", dhw=True, **HOURS_TOTAL),
    _d("hw_compressor_runtime", "hmu.RunStatsCompressorHwc", field=RUNSTATS_HWC_RUNTIME, dhw=True,
       device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES,
       state_class=SensorStateClass.TOTAL_INCREASING, **DIAG),
    _d("hw_compressor_cycles", "hmu.RunStatsCompressorHwc", field=RUNSTATS_HWC_CYCLES, dhw=True,
       state_class=SensorStateClass.TOTAL_INCREASING, **DIAG),
    _d("hw_controller_electricity_total", "basv.PrEnergySumHwc", device=DEVICE_CONTROLLER, dhw=True,
       **{**KWH_TOTAL, **DIAG}),
    _d("hw_controller_electricity_this_month", "basv.PrEnergySumHwcThisMonth",
       device=DEVICE_CONTROLLER, dhw=True, **{**KWH_TOTAL, **DIAG}),
    _d("hw_controller_electricity_last_month", "basv.PrEnergySumHwcLastMonth",
       device=DEVICE_CONTROLLER, dhw=True, device_class=SensorDeviceClass.ENERGY,
       native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, **DIAG),
    _d("signal_drops_today", None, device=DEVICE_EBUSD, bus=False,
       value_fn=lambda c: c.derived.signal_drops_day,
       state_class=SensorStateClass.TOTAL_INCREASING, **DIAG),
    _d("symbol_rate", None, device=DEVICE_EBUSD, bus=False,
       value_fn=lambda c: c.status.symbolrate, native_unit_of_measurement="symbols/s",
       state_class=SensorStateClass.MEASUREMENT, **DIAG),
    _d("bus_reads_per_minute", None, device=DEVICE_EBUSD, bus=False,
       value_fn=lambda c: c.bus_reads_per_minute(),
       state_class=SensorStateClass.MEASUREMENT, **DIAG),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArothermConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ArothermSensor(coordinator, desc) for desc in SENSORS if coordinator.dhw or not desc.dhw
    )


class ArothermSensor(ArothermEntity, SensorEntity):
    """A sensor backed by an ebusd field or a derived value."""

    entity_description: ArothermSensorDescription

    def __init__(self, coordinator: ArothermCoordinator, desc: ArothermSensorDescription) -> None:
        super().__init__(coordinator, desc.key, desc.device, desc.msg, desc.bus)
        self.entity_description = desc

    @property
    def native_value(self) -> Any:
        desc = self.entity_description
        if desc.value_fn is not None:
            return desc.value_fn(self.coordinator)
        if desc.device_class == SensorDeviceClass.ENUM:
            return self.coordinator.field(desc.msg, desc.field)
        return self.coordinator.num(desc.msg, desc.field)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        desc = self.entity_description
        return desc.attrs_fn(self.coordinator) if desc.attrs_fn else None
