"""Derived values: COP, electricity integration, compressor cycle statistics.

Home Assistant independent (plain Python) so it can be unit-tested directly.
All timestamps are UNIX seconds; period keys ("2026-10-28", "2026-10") are
supplied by the caller in local time.

arotherm_ebusd - version 0.3.0 (2026-10-28)

Changelog:
  0.1.0 (2026-10-28) - Initial release.
  0.2.0 (2026-10-28) - Version bump only; no functional change.
  0.2.1 (2026-10-28) - Version bump only; no functional change.
  0.2.2 (2026-10-28) - Version bump only; no functional change.
  0.3.0 (2026-10-28) - Version bump only; no functional change.
"""

from __future__ import annotations

from collections import deque
from typing import Any

MAX_GAP_S = 180.0            # don't integrate across gaps longer than this
COP_WINDOW_S = 15 * 60.0     # smoothed COP window
COP_MIN_ELEC_KWH = 0.02      # need >= ~80 W average over the window
LIVE_COP_MIN_W = 100.0       # ignore standby power for live COP
COP_SANITY_MAX = 10.0
START_WINDOW_S = 3600.0
MAX_PLAUSIBLE_START_DELTA = 50


class Derived:
    """Accumulates derived heat pump statistics."""

    def __init__(self, sc_starts: int = 3, sc_min_run_s: float = 600.0) -> None:
        self.sc_starts = sc_starts
        self.sc_min_run_s = sc_min_run_s
        # electricity (integrated from the heat pump's own W reading)
        self.elec_total_kwh = 0.0
        self.elec_day_kwh = 0.0
        self.elec_month_kwh = 0.0
        self.day_key: str | None = None
        self.month_key: str | None = None
        self.day_partial = True      # tracking started part-way through the day
        self.month_partial = True
        self._last_power: tuple[float, float] | None = None  # (ts, W)
        self._window: deque[tuple[float, float, float]] = deque()  # (ts, heat kW, elec W)
        # compressor starts (from the HP's CompressorStarts counter)
        self.last_counter: int | None = None
        self.last_counter_ts: float | None = None
        self.starts_base_day: int | None = None
        self.starts_base_month: int | None = None
        self.counter_starts: list[float] = []   # timestamps of counted starts
        self.edge_starts: list[float] = []      # timestamps of detected off->on edges
        # running / run time
        self.running: bool | None = None
        self.run_started: float | None = None
        self._last_run_tick: float | None = None
        self.runtime_day_s = 0.0
        self.last_run_s: float | None = None
        self.last_run_end: float | None = None
        # bus
        self._last_signal: bool | None = None
        self.signal_drops_day = 0

    # ------------------------------------------------------------------ periods
    def roll_periods(self, day_key: str, month_key: str) -> None:
        """Reset daily/monthly accumulators when the local date changes."""
        if self.day_key is None:
            self.day_key, self.month_key = day_key, month_key
            return
        if day_key != self.day_key:
            self.day_key = day_key
            self.elec_day_kwh = 0.0
            self.runtime_day_s = 0.0
            self.signal_drops_day = 0
            self.day_partial = False
            self.starts_base_day = self.last_counter
        if month_key != self.month_key:
            self.month_key = month_key
            self.elec_month_kwh = 0.0
            self.month_partial = False
            self.starts_base_month = self.last_counter

    # ------------------------------------------------------------------ power
    def add_power_sample(self, ts: float, elec_w: float | None, heat_kw: float | None) -> None:
        """Add one (electric W, heat kW) sample taken at ts."""
        if elec_w is None:
            self._last_power = None
            return
        if self._last_power is not None:
            last_ts, last_w = self._last_power
            dt = ts - last_ts
            if 0 < dt <= MAX_GAP_S:
                kwh = (elec_w + last_w) / 2.0 * dt / 3_600_000.0
                self.elec_total_kwh += kwh
                self.elec_day_kwh += kwh
                self.elec_month_kwh += kwh
            elif dt <= 0:
                return  # same or older sample: ignore
        self._last_power = (ts, elec_w)
        if heat_kw is not None:
            self._window.append((ts, heat_kw, elec_w))
        while self._window and ts - self._window[0][0] > COP_WINDOW_S:
            self._window.popleft()

    def cop_window(self) -> float | None:
        """COP over the last 15 minutes (energy-weighted)."""
        heat_kwh = elec_kwh = 0.0
        prev = None
        for sample in self._window:
            if prev is not None:
                dt = sample[0] - prev[0]
                if 0 < dt <= MAX_GAP_S:
                    heat_kwh += (sample[1] + prev[1]) / 2.0 * dt / 3600.0
                    elec_kwh += (sample[2] + prev[2]) / 2.0 * dt / 3_600_000.0
            prev = sample
        if elec_kwh < COP_MIN_ELEC_KWH:
            return None
        cop = heat_kwh / elec_kwh
        return round(cop, 2) if 0 <= cop <= COP_SANITY_MAX else None

    @staticmethod
    def cop_live(heat_kw: float | None, elec_w: float | None, running: bool | None) -> float | None:
        """Instantaneous COP, only while the compressor is running."""
        if not running or heat_kw is None or elec_w is None or elec_w < LIVE_COP_MIN_W:
            return None
        cop = heat_kw * 1000.0 / elec_w
        return round(cop, 2) if 0 <= cop <= COP_SANITY_MAX else None

    @staticmethod
    def cop_period(heat_kwh: float | None, elec_kwh: float) -> float | None:
        """COP for a period (heat from the HP's counters / integrated electricity)."""
        if heat_kwh is None or elec_kwh < 0.1:
            return None
        cop = heat_kwh / elec_kwh
        return round(cop, 2) if 0 <= cop <= COP_SANITY_MAX else None

    # ------------------------------------------------------------------ starts
    def update_counter(self, ts: float, counter: float | None) -> None:
        """Feed the CompressorStarts counter."""
        if counter is None:
            return
        value = int(counter)
        if self.last_counter is not None:
            delta = value - self.last_counter
            if 0 < delta < MAX_PLAUSIBLE_START_DELTA:
                self.counter_starts.extend([ts] * delta)
            elif delta < 0 or delta >= MAX_PLAUSIBLE_START_DELTA:
                # counter reset or glitch: re-baseline
                self.starts_base_day = self.starts_base_month = value
        if self.starts_base_day is None:
            self.starts_base_day = value
        if self.starts_base_month is None:
            self.starts_base_month = value
        self.last_counter = value
        self.last_counter_ts = ts
        self._prune(ts)

    def _prune(self, now: float) -> None:
        self.counter_starts = [t for t in self.counter_starts if now - t <= START_WINDOW_S]
        self.edge_starts = [t for t in self.edge_starts if now - t <= START_WINDOW_S]

    def starts_today(self) -> int | None:
        if self.last_counter is None or self.starts_base_day is None:
            return None
        return max(0, self.last_counter - self.starts_base_day)

    def starts_month(self) -> int | None:
        if self.last_counter is None or self.starts_base_month is None:
            return None
        return max(0, self.last_counter - self.starts_base_month)

    def starts_last_hour(self, now: float) -> int:
        """Starts in the last 60 min: counter-based if the counter is current."""
        self._prune(now)
        if self.last_counter_ts is not None and now - self.last_counter_ts <= 900:
            return len(self.counter_starts)
        return len(self.edge_starts)

    # ------------------------------------------------------------------ running
    def update_running(self, ts: float, running: bool | None) -> None:
        """Feed the compressor running state (None = unknown)."""
        if running is None:
            self._last_run_tick = None
            return
        if self.running and self._last_run_tick is not None:
            # count the interval up to this observation (also when it shows 'stopped',
            # so run time matches the last-run length measured to the same tick)
            dt = ts - self._last_run_tick
            if 0 < dt <= MAX_GAP_S:
                self.runtime_day_s += dt
        if running and self.running is False:
            self.run_started = ts
            self.edge_starts.append(ts)
        elif not running and self.running and self.run_started is not None:
            self.last_run_s = ts - self.run_started
            self.last_run_end = ts
            self.run_started = None
        elif not running:
            self.run_started = None
        self.running = running
        self._last_run_tick = ts

    def avg_run_today_s(self) -> float | None:
        starts = self.starts_today()
        if not starts:
            return None
        return self.runtime_day_s / starts

    def short_cycling(self, now: float) -> bool:
        if self.starts_last_hour(now) >= self.sc_starts:
            return True
        return (
            self.last_run_s is not None
            and self.last_run_end is not None
            and self.last_run_s < self.sc_min_run_s
            and now - self.last_run_end <= START_WINDOW_S
        )

    # ------------------------------------------------------------------ bus
    def update_signal(self, signal: bool | None) -> None:
        if signal is None:
            return
        if self._last_signal and not signal:
            self.signal_drops_day += 1
        self._last_signal = signal

    # ------------------------------------------------------------------ persistence
    _PERSIST = (
        "elec_total_kwh", "elec_day_kwh", "elec_month_kwh", "day_key", "month_key",
        "day_partial", "month_partial", "last_counter", "last_counter_ts",
        "starts_base_day", "starts_base_month", "counter_starts", "edge_starts",
        "runtime_day_s", "last_run_s", "last_run_end", "signal_drops_day",
    )

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self._PERSIST}

    def load(self, data: dict[str, Any] | None) -> None:
        if not data:
            return
        for k in self._PERSIST:
            if k in data:
                setattr(self, k, data[k])
