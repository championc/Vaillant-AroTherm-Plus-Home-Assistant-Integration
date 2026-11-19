"""Data update coordinator for aroTHERM ebusd.

Polling model (one coordinator tick every `tier_fast` seconds):
  * active messages are read with TCP 'read -m <maxage>' only when their tier
    is due; ebusd answers from cache when the value is fresh enough, so the
    bus is only touched when needed;
  * passive messages (refreshed by the VRC 720 / VWZIO traffic) are taken from
    ebusd's cache via HTTP/JSON (or TCP 'read -m 900' if HTTP is unavailable);
  * if ebusd is unreachable the update fails once (all entities unavailable,
    one log line) and recovers automatically on a later tick;
  * if ebusd has no eBUS signal for longer than SIGNAL_GRACE (2 min), bus
    values go unavailable but the ebusd entities stay available; shorter
    dropouts only pause polling.

Writes go through async_write(), which is off unless enabled in options,
supports a dry-run mode, rate-limits, checks bounds, reads the old value,
sends exactly one write and verifies it by reading back from the bus.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Every write (and dry run) is added to the logbook; writers pass entity_id.
  0.2.1 (2026-10-28) - Signal grace period: dropouts shorter than 2 min no longer make bus entities unavailable (polling pauses meanwhile).
  0.2.2 (2026-10-28) - Every value is plausibility-checked before use; counters must not fall or jump unless confirmed by a second read; compressor running now decided by status code (or modulation AND speed).
  0.3.0 (2026-10-28) - Polls DHW messages only when the option is on; heat today/month include hot water yield when DHW is on.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .catalog import (
    COUNTERS,
    MESSAGES,
    MESSAGES_BY_KEY,
    PLAUSIBLE,
    STATE00_COMPRESSORSTATE,
    STATE00_RUNNING,
    STATUS_RUNNING,
    VDATETIME_DATE,
    VDATETIME_TIME,
    WRITABLE_NUMBERS,
    WRITABLE_SELECTS,
    Msg,
)
from .const import (
    CONF_HTTP_PORT,
    CONF_SC_MIN_RUN,
    CONF_SC_STARTS,
    CONF_TCP_PORT,
    CONF_TIER_FAST,
    CONF_WRITE_DRY_RUN,
    CONF_DHW,
    CONF_WRITES_ENABLED,
    DEFAULT_OPTIONS,
    DOMAIN,
    PASSIVE_INTERVAL,
    PASSIVE_MAXAGE,
    SENTINEL_VALUES,
    SIGNAL_GRACE,
    STORAGE_SAVE_DELAY,
    STORAGE_VERSION,
    TIER_OPTION,
    TIER_PASSIVE,
    WRITE_MIN_INTERVAL,
)
from .derived import Derived
from .ebusd_client import (
    EbusdCommandError,
    EbusdConnectionError,
    EbusdHttpClient,
    EbusdNoSignal,
    EbusdTcpClient,
    format_write_value,
    parse_http_circuit,
)

_LOGGER = logging.getLogger(__name__)

type ArothermConfigEntry = ConfigEntry[ArothermCoordinator]


@dataclass
class MsgState:
    """Last known state of one message."""

    values: list[Any] | None = None
    updated: float | None = None       # UNIX time the value was (re)confirmed
    error: str | None = None
    error_time: float | None = None
    ok_count: int = 0
    error_count: int = 0
    source: str | None = None          # "http" (has ebusd's receive time) or "tcp"
    rejected_count: int = 0
    last_rejected: str | None = None
    pending: list[Any] | None = None   # counter reading waiting for confirmation


@dataclass
class EbusdStatus:
    """ebusd daemon / bus status."""

    reachable: bool = False
    signal: bool | None = None
    signal_lost_since: float | None = None   # monotonic
    symbolrate: int | None = None
    maxsymbolrate: int | None = None
    reconnects: int | None = None
    version: str | None = None
    http_ok: bool | None = None
    info: dict[str, Any] = field(default_factory=dict)


class ArothermCoordinator(DataUpdateCoordinator[dict[str, MsgState]]):
    """Polls ebusd and owns the derived statistics."""

    config_entry: ArothermConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ArothermConfigEntry) -> None:
        self.options: dict[str, Any] = {**DEFAULT_OPTIONS, **entry.options}
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.options[CONF_TIER_FAST]),
        )
        host = entry.data[CONF_HOST]
        self.tcp = EbusdTcpClient(host, entry.data[CONF_TCP_PORT])
        http_port = entry.data.get(CONF_HTTP_PORT) or 0
        self.http: EbusdHttpClient | None = (
            EbusdHttpClient(async_get_clientsession(hass), host, http_port)
            if http_port
            else None
        )
        self.dhw: bool = bool(self.options.get(CONF_DHW))
        self.messages: tuple[Msg, ...] = tuple(m for m in MESSAGES if self.dhw or not m.dhw)
        self.msgs: dict[str, MsgState] = {m.key: MsgState() for m in MESSAGES}
        self._next_due: dict[str, float] = {m.key: 0.0 for m in self.messages}
        self.status = EbusdStatus()
        self.derived = Derived(
            sc_starts=int(self.options[CONF_SC_STARTS]),
            sc_min_run_s=float(self.options[CONF_SC_MIN_RUN]) * 60.0,
        )
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._bus_reads: deque[float] = deque()
        self._last_power_ts: float | None = None
        self._last_write = 0.0
        self.write_log: deque[dict[str, Any]] = deque(maxlen=20)

    # ------------------------------------------------------------------ setup
    async def async_load(self) -> None:
        """Load persisted derived state and ebusd 'info'."""
        self.derived.load(await self._store.async_load())
        try:
            self.status.info = await self.tcp.info()
            self.status.version = self.status.info.get("version")
        except EbusdConnectionError as err:
            _LOGGER.debug("info not available yet: %s", err)

    async def async_shutdown(self) -> None:
        """Persist and close."""
        await self._store.async_save(self.derived.to_dict())
        await self.tcp.close()
        await super().async_shutdown()

    def _interval(self, msg: Msg) -> int:
        if msg.tier == TIER_PASSIVE:
            return PASSIVE_INTERVAL
        return int(self.options[TIER_OPTION[msg.tier]])

    # ------------------------------------------------------------------ polling
    async def _async_update_data(self) -> dict[str, MsgState]:
        now_mono = time.monotonic()
        try:
            await self._refresh_status()
            if self.status.signal:
                await self._poll_passive(now_mono)
                await self._poll_active(now_mono)
        except EbusdConnectionError as err:
            self.status.reachable = False
            self.derived.update_signal(None)
            raise UpdateFailed(f"ebusd not reachable: {err}") from err
        self.status.reachable = True
        self._update_derived()
        self._store.async_delay_save(self.derived.to_dict, STORAGE_SAVE_DELAY)
        return self.msgs

    async def _refresh_status(self) -> None:
        """Update signal/symbol rate; HTTP 'global' block preferred, TCP 'state' fallback."""
        state: dict[str, Any] | None = None
        if self.http is not None:
            try:
                payload = await self.http.get_circuit("broadcast")
                self.status.http_ok = True
                self._ingest_http(payload, "broadcast")
                glob = payload.get("global")
                if isinstance(glob, dict) and "signal" in glob:
                    state = glob
            except EbusdConnectionError as err:
                if self.status.http_ok is not False:
                    _LOGGER.debug("HTTP unavailable, using TCP only: %s", err)
                self.status.http_ok = False
        if state is None:
            state = await self.tcp.state()
        self._set_signal(bool(state.get("signal")))
        self.status.symbolrate = state.get("symbolrate")
        self.status.maxsymbolrate = state.get("maxsymbolrate")
        self.status.reconnects = state.get("reconnects", self.status.reconnects)
        if v := state.get("version"):
            self.status.version = v
        self.derived.update_signal(self.status.signal)

    def _set_signal(self, signal: bool) -> None:
        if signal:
            self.status.signal_lost_since = None
        elif self.status.signal_lost_since is None:
            self.status.signal_lost_since = time.monotonic()
        self.status.signal = signal

    def bus_ok(self) -> bool:
        """Bus considered usable: signal present, or lost for less than SIGNAL_GRACE."""
        if self.status.signal:
            return True
        lost = self.status.signal_lost_since
        return lost is not None and time.monotonic() - lost < SIGNAL_GRACE

    def _ingest_http(self, payload: dict[str, Any], circuit: str) -> None:
        """Store passive values found in an HTTP payload."""
        now = time.time()
        for name, item in parse_http_circuit(payload, circuit).items():
            key = f"{circuit}.{name}"
            msg = MESSAGES_BY_KEY.get(key)
            if msg is None or msg.tier != TIER_PASSIVE:
                continue
            lastup = item.get("lastup")
            if isinstance(lastup, (int, float)) and now - lastup > PASSIVE_MAXAGE:
                continue  # too old; TCP fallback will refresh it
            ts = float(lastup) if isinstance(lastup, (int, float)) else now
            self._accept(key, item["values"], ts,
                         "http" if isinstance(lastup, (int, float)) else "tcp")

    async def _poll_passive(self, now_mono: float) -> None:
        passive = [m for m in self.messages if m.tier == TIER_PASSIVE]
        if not any(self._next_due[m.key] <= now_mono for m in passive):
            return
        if self.http is not None and self.status.http_ok:
            try:
                self._ingest_http(await self.http.get_circuit("hmu"), "hmu")
            except EbusdConnectionError:
                self.status.http_ok = False
        now = time.time()
        for msg in passive:
            st = self.msgs[msg.key]
            if st.updated is None or now - st.updated > PASSIVE_MAXAGE:
                # not in cache (or HTTP off): ask ebusd, bus only if older than maxage
                await self._read(msg, PASSIVE_MAXAGE)
            self._next_due[msg.key] = now_mono + PASSIVE_INTERVAL

    async def _poll_active(self, now_mono: float) -> None:
        for msg in self.messages:
            if msg.tier == TIER_PASSIVE or self._next_due[msg.key] > now_mono:
                continue
            interval = self._interval(msg)
            ok = await self._read(msg, max(5, interval - 5))
            # on error retry sooner, but not more often than once a minute
            self._next_due[msg.key] = now_mono + (interval if ok else min(interval, 60))
            if self.status.signal is False:
                break

    async def _read(self, msg: Msg, maxage: int) -> bool:
        st = self.msgs[msg.key]
        try:
            values = await self.tcp.read(msg.circuit, msg.name, maxage=maxage)
        except EbusdNoSignal as err:
            self._set_signal(False)
            self.derived.update_signal(False)
            _LOGGER.debug("no eBUS signal while reading %s: %s", msg.key, err)
            return False
        except EbusdCommandError as err:
            st.error, st.error_time = str(err), time.time()
            st.error_count += 1
            _LOGGER.debug("read %s failed: %s", msg.key, err)
            return False
        self._bus_reads.append(time.monotonic())
        return self._accept(msg.key, values, time.time(), "tcp")

    def _accept(self, key: str, values: list[Any], ts: float, source: str) -> bool:
        """Store a value if it passes the plausibility checks; else keep the old one."""
        st = self.msgs[key]
        reason = self._implausible(key, values, st)
        if reason is not None:
            st.rejected_count += 1
            st.last_rejected = f"{dt_util.now().isoformat(timespec='seconds')} {values} ({reason})"
            _LOGGER.debug("rejected %s = %s: %s", key, values, reason)
            return False
        st.values, st.updated, st.error, st.source, st.pending = values, ts, None, source, None
        st.ok_count += 1
        return True

    @staticmethod
    def _implausible(key: str, values: list[Any], st: MsgState) -> str | None:
        """Return why a reading is implausible, or None if it is fine."""
        for idx, (lo, hi) in PLAUSIBLE.get(key, {}).items():
            v = values[idx] if idx < len(values) else None
            if isinstance(v, (int, float)) and not lo <= float(v) <= hi:
                if v in SENTINEL_VALUES:
                    continue  # "not fitted" marker, handled as None later
                return f"field {idx} = {v} outside {lo}..{hi}"
        if key in COUNTERS and values and isinstance(values[0], (int, float)):
            new = float(values[0])
            prev = st.values[0] if st.values and isinstance(st.values[0], (int, float)) else None
            if prev is not None:
                step = COUNTERS[key]
                if new < prev or new - prev > step:
                    pend = st.pending[0] if st.pending else None
                    if isinstance(pend, (int, float)) and abs(new - float(pend)) <= step:
                        return None  # confirmed by a second, consistent read
                    st.pending = values
                    return f"counter {prev:g} -> {new:g} not plausible (held for confirmation)"
        return None

    # ------------------------------------------------------------------ values
    def is_fresh(self, key: str) -> bool:
        """True if the message has a value that is not stale."""
        st = self.msgs.get(key)
        if st is None or st.values is None or st.updated is None:
            return False
        msg = MESSAGES_BY_KEY[key]
        limit = PASSIVE_MAXAGE * 2 if msg.tier == TIER_PASSIVE else 3 * self._interval(msg) + 60
        return time.time() - st.updated <= limit

    def field(self, key: str, index: int = 0) -> Any:
        """Return one field value (None if missing, stale or a 'not fitted' sentinel)."""
        if not self.is_fresh(key):
            return None
        values = self.msgs[key].values or []
        if index >= len(values):
            return None
        value = values[index]
        if isinstance(value, float) and value in SENTINEL_VALUES:
            return None
        return value

    def num(self, key: str, index: int = 0) -> float | None:
        """Return a numeric field value or None."""
        value = self.field(key, index)
        return float(value) if isinstance(value, (int, float)) else None

    def compressor_running(self) -> bool | None:
        """Best available view of whether the compressor runs."""
        # 0.2.2: the heat pump's status code decides when it is available;
        # otherwise modulation AND speed must both show the compressor turning
        # (a single corrupt value can no longer fake a run); State00 is last.
        status = self.field("hmu.Statuscode")
        if isinstance(status, str):
            return any(s in status for s in STATUS_RUNNING)
        modulation = self.num("hmu.CompressorModulation")
        speed = self.num("hmu.CompressorSpeed")
        if modulation is not None and speed is not None:
            return modulation > 0 and speed > 0
        cstate = self.field("hmu.State00", STATE00_COMPRESSORSTATE)
        if isinstance(cstate, str):
            return cstate in STATE00_RUNNING
        return None

    def controller_clock(self) -> tuple[str | None, float | None]:
        """VRC 720 broadcast time as text, and its drift vs HA in minutes.

        The drift is only computed when ebusd's own receive time is known
        (HTTP lastup); in TCP-only mode the cached value's age is unknown.
        """
        tval = self.field("broadcast.vdatetime", VDATETIME_TIME)
        dval = self.field("broadcast.vdatetime", VDATETIME_DATE)
        if not isinstance(tval, str) or not isinstance(dval, str):
            return None, None
        text = f"{dval} {tval}"
        st = self.msgs["broadcast.vdatetime"]
        if st.source != "http" or st.updated is None:
            return text, None
        try:
            ctrl = datetime.strptime(text, "%d.%m.%Y %H:%M:%S").replace(
                tzinfo=dt_util.get_default_time_zone()
            )
        except ValueError:
            return text, None
        return text, round((ctrl.timestamp() - st.updated) / 60.0, 1)

    def heat_today(self) -> float | None:
        """Heat produced today: heating + hot water (if DHW is enabled)."""
        hc = self.num("hmu.YieldHcDay")
        if hc is None or not self.dhw:
            return hc
        hw = self.num("hmu.YieldHwcDay")
        return None if hw is None else hc + hw

    def heat_month(self) -> float | None:
        """Heat produced this month: heating + hot water (if DHW is enabled)."""
        hc = self.num("hmu.YieldHcMonth")
        if hc is None or not self.dhw:
            return hc
        hw = self.num("hmu.YieldHwcMonth")
        return None if hw is None else hc + hw

    def errors(self, circuit: str) -> list[int] | None:
        """Active error numbers reported by a circuit ([] = none)."""
        key = f"{circuit}.currenterror"
        if not self.is_fresh(key):
            return None
        return [int(v) for v in (self.msgs[key].values or []) if isinstance(v, (int, float))]

    def bus_reads_per_minute(self) -> int:
        now = time.monotonic()
        while self._bus_reads and now - self._bus_reads[0] > 60:
            self._bus_reads.popleft()
        return len(self._bus_reads)

    def _update_derived(self) -> None:
        now = time.time()
        local = dt_util.now()
        self.derived.roll_periods(local.strftime("%Y-%m-%d"), local.strftime("%Y-%m"))
        pst = self.msgs["hmu.CurrentConsumedPowerWatt"]
        if pst.updated is not None and pst.updated != self._last_power_ts:
            self._last_power_ts = pst.updated
            self.derived.add_power_sample(
                pst.updated,
                self.num("hmu.CurrentConsumedPowerWatt"),
                self.num("hmu.CurrentYieldPower"),
            )
        self.derived.update_counter(now, self.num("hmu.CompressorStarts"))
        self.derived.update_running(now, self.compressor_running())

    # ------------------------------------------------------------------ writes
    def _logbook(self, entity_id: str | None, message: str) -> None:
        """Add a logbook line (the logbook integration listens for this event)."""
        self.hass.bus.async_fire(
            "logbook_entry",
            {"name": "aroTHERM ebusd", "message": message, "domain": DOMAIN,
             **({"entity_id": entity_id} if entity_id else {})},
        )

    async def async_write(
        self, key: str, value: Any, *, chained: bool = False, entity_id: str | None = None
    ) -> None:
        """Guarded write of one value. Raises HomeAssistantError on any problem.

        chained=True is only used for the second write of one user action
        (climate quick veto) and skips the between-writes rate limit.
        """
        msg = MESSAGES_BY_KEY.get(key)
        if msg is not None and msg.dhw and not self.dhw:
            msg = None
        if msg is None or (key not in WRITABLE_NUMBERS and key not in WRITABLE_SELECTS):
            raise HomeAssistantError(f"{key} is not writable in this integration")
        if not self.options.get(CONF_WRITES_ENABLED):
            raise HomeAssistantError(
                "Writing is disabled. Enable it in the aroTHERM ebusd integration options."
            )
        self._validate(key, value)
        text = format_write_value(value)
        cmd = f"write -c {msg.circuit} {msg.name} {text}"

        if not chained and time.monotonic() - self._last_write < WRITE_MIN_INTERVAL:
            raise HomeAssistantError("Please wait a few seconds between writes")

        try:
            old = await self.tcp.read(msg.circuit, msg.name, force=True)
        except (EbusdCommandError, EbusdNoSignal, EbusdConnectionError) as err:
            raise HomeAssistantError(f"Could not read current {key} before writing: {err}") from err
        old_v = old[0] if old else None
        if key in WRITABLE_NUMBERS and isinstance(old_v, (int, float)):
            spec = WRITABLE_NUMBERS[key]
            if spec.max_change is not None and abs(float(value) - old_v) > spec.max_change + 1e-9:
                raise HomeAssistantError(
                    f"Refusing to change {key} from {old_v} to {value}: more than "
                    f"{spec.max_change} in one step"
                )
        entry = {"time": dt_util.now().isoformat(), "key": key, "command": cmd,
                 "old": old_v, "new": value}
        self._last_write = time.monotonic()

        if self.options.get(CONF_WRITE_DRY_RUN, True):
            entry["result"] = "dry-run (not sent)"
            self.write_log.append(entry)
            _LOGGER.warning("DRY RUN - would send '%s' (current value %s)", cmd, old_v)
            self._logbook(entity_id, f"dry run, not sent: {cmd} (current {old_v})")
            persistent_notification.async_create(
                self.hass,
                f"Dry run - nothing was sent.\n\nCommand: `{cmd}`\n\n"
                f"Current value: **{old_v}**\nRequested value: **{value}**",
                title="aroTHERM ebusd write (dry run)",
                notification_id=f"{DOMAIN}_dry_run",
            )
            return

        try:
            answer = await self.tcp.write(msg.circuit, msg.name, value)
            new = await self.tcp.read(msg.circuit, msg.name, force=True)
        except (EbusdCommandError, EbusdNoSignal, EbusdConnectionError) as err:
            entry["result"] = f"error: {err}"
            self.write_log.append(entry)
            _LOGGER.error("Write '%s' failed: %s", cmd, err)
            raise HomeAssistantError(f"Write {key} failed: {err}") from err

        new_v = new[0] if new else None
        ok = (
            abs(float(new_v) - float(value)) <= 0.05
            if isinstance(new_v, (int, float)) and isinstance(value, (int, float))
            else new_v == value
        )
        entry["result"] = f"{'verified' if ok else 'NOT verified'} (ebusd: {answer}, read back {new_v})"
        self.write_log.append(entry)
        st = self.msgs[key]
        st.values, st.updated, st.error = new, time.time(), None
        self.async_update_listeners()
        self._logbook(
            entity_id,
            f"changed {msg.name} from {old_v} to {new_v}"
            + ("" if ok else f" - NOT verified (requested {value})"),
        )
        if not ok:
            _LOGGER.error("Write '%s' sent but read back %s", cmd, new_v)
            raise HomeAssistantError(f"{key}: wrote {value} but read back {new_v}")
        _LOGGER.info("Wrote %s: %s -> %s (verified)", key, old_v, new_v)

    @staticmethod
    def _validate(key: str, value: Any) -> None:
        if key in WRITABLE_NUMBERS:
            spec = WRITABLE_NUMBERS[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise HomeAssistantError(f"{key} needs a number")
            if not spec.min_value <= float(value) <= spec.max_value:
                raise HomeAssistantError(
                    f"{key} must be between {spec.min_value} and {spec.max_value}"
                )
            steps = round((float(value) - spec.min_value) / spec.step, 6)
            if abs(steps - round(steps)) > 1e-6:
                raise HomeAssistantError(f"{key} must be in steps of {spec.step}")
        else:
            if value not in WRITABLE_SELECTS[key]:
                raise HomeAssistantError(f"{key}: '{value}' is not an allowed option")
