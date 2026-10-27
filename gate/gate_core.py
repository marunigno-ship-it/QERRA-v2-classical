# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- pure-function core (SAFETY_CONCEPT.md v0.2).

    step(state, params, inputs) -> StepResult

Rules this module follows (see SAFETY_CONCEPT.md):
  AR-2  A proposal can only be clamped DOWN into the gate envelope, never raised.
  AR-3  Parameters live in an immutable GateParams. No input can change them.
  AR-7  Lidar data is validated before use. Invalid data is a trip, never a default.
  AR-8  This module is a pure function. No sockets, no files, no Webots, no clock,
        no randomness. Time arrives as `inputs.sim_time_us`. It uses strictly the
        Python standard library with zero external dependencies.
  AR-9  Obstacle hazard evaluation is a deterministic stopping envelope check:
        hazard = (min_range <= d_stop).
        The latch, dwell, and reset logic below enforces fail-closed recovery.

Units are integers everywhere that is logged:
  time        microseconds (sim time)
  wheel speed micro-radians per second (urad/s)
  distance    millimetres
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Sequence, Tuple

GATE_CORE_VERSION = "0.3"

# Reset sources. Only the exact string "operator" is ever accepted (AR-4).
RESET_SOURCE_OPERATOR = "operator"
RESET_SOURCE_PROPOSER = "proposer"

# Sanity bound for proposal wheel speeds before clamping (urad/s).
_WHEEL_SANITY_LIMIT = 10 ** 12


class Mode(str, Enum):
    RUN = "RUN"
    TRIPPED = "TRIPPED"
    AWAITING_RESET = "AWAITING_RESET"


class Reason:
    """Primary reason for this tick's decision (one value per tick)."""
    PASS = "PASS"
    TRIP_OBSTACLE = "TRIP_OBSTACLE"
    TRIP_PROPOSER_DEAD = "TRIP_PROPOSER_DEAD"      # no valid proposal ever accepted
    TRIP_PROPOSER_STALE = "TRIP_PROPOSER_STALE"    # newest proposal age >= T_watch
    TRIP_SENSOR_INVALID = "TRIP_SENSOR_INVALID"
    TRIP_HSR_CRITICAL = "TRIP_HSR_CRITICAL"        # acute physical distress / hazard reflex
    TRIP_HSR_INVALID = "TRIP_HSR_INVALID"          # missing or corrupted HSR telemetry
    TRIP_HSR_STALE = "TRIP_HSR_STALE"              # HSR heartbeat age >= t_hsr_stale
    TRIP_LOG_FAILURE = "TRIP_LOG_FAILURE"
    TRIP_CLOCK_ANOMALY = "TRIP_CLOCK_ANOMALY"      # sim time did not strictly increase
    LATCHED_DWELL = "LATCHED_DWELL"                # tripped, waiting for T_dwell of continuous clear
    LATCHED_AWAIT_RESET = "LATCHED_AWAIT_RESET"    # dwell done, waiting for operator reset
    RESET_ACCEPTED = "RESET_ACCEPTED"


class Event:
    """Secondary events on this tick (zero or more)."""
    MSG_REJECTED_INVALID = "MSG_REJECTED_INVALID"
    MSG_REJECTED_SEQ = "MSG_REJECTED_SEQ"
    MSG_REJECTED_FUTURE = "MSG_REJECTED_FUTURE"
    RESET_REJECTED_CHANNEL = "RESET_REJECTED_CHANNEL"
    RESET_REJECTED_HAZARD = "RESET_REJECTED_HAZARD"
    RESET_REJECTED_NOT_READY = "RESET_REJECTED_NOT_READY"
    RESET_IGNORED_RUN = "RESET_IGNORED_RUN"


# ----------------------------------------------------------------------------
# Parameters (AR-3: immutable)
# ----------------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class GateParams:
    # REQUIRED: number of lidar samples in the forward cone the shell must pass.
    lidar_n_expected: int

    dt_us: int = 32_000                 # Webots basicTimeStep (32 ms)
    t_watch_us: int = 150_000           # proposer freshness limit (150 ms, accommodating Windows thread jitter)
    proposer_period_us: int = 33_000    # proposer send period; <= t_watch/3
    lidar_period_us: int = 32_000       # Hokuyo sampling period matching dt
    t_stale_us: int = 96_000            # lidar freshness limit (3 * dt)
    t_dwell_us: int = 1_000_000         # continuous-clear time before reset is possible (1.0 s)
    max_tick_gap_us: int = 64_000       # gap between ticks that still counts as continuous

    wheel_radius_mm: int = 98           # TIAGo base wheel radius (98 mm)
    w_min_urad_s: int = 0               # no reverse (no rear sensor)
    w_max_urad_s: int = 3_000_000       # envelope cap: 3.0 rad/s per wheel
    a_design_mmps2: int = 500           # design deceleration: 500 mm/s² (0.5 m/s²)
    margin_mm: int = 300                # safety standoff margin: 300 mm
    min_raw_lidar_returns: int = 5      # minimum valid raw returns required for sensor liveness
    t_react_us: int = 0                 # reaction time allowance; defaults to 0 for backward-compatibility (F4)
    hsr_required: bool = False          # False = legacy/Demo 8 mode; True = fail-closed if HSR missing (Demo 9)
    t_hsr_stale_us: int = 96_000        # HSR freshness limit (3 * dt = 96 ms)

    def __post_init__(self) -> None:
        for name in (
            "lidar_n_expected", "dt_us", "t_watch_us", "proposer_period_us",
            "lidar_period_us", "t_stale_us", "t_dwell_us", "max_tick_gap_us",
            "wheel_radius_mm", "w_max_urad_s", "a_design_mmps2", "t_hsr_stale_us",
        ):
            value = getattr(self, name)
            if not _is_int(value) or value <= 0:
                raise ValueError(f"GateParams.{name} must be a positive int, got {value!r}")
        for name in ("w_min_urad_s", "margin_mm", "min_raw_lidar_returns", "t_react_us"):
            value = getattr(self, name)
            if not _is_int(value) or value < 0:
                raise ValueError(f"GateParams.{name} must be a non-negative int, got {value!r}")
        if not isinstance(self.hsr_required, bool):
            raise ValueError(f"GateParams.hsr_required must be a bool, got {self.hsr_required!r}")
        if self.w_min_urad_s > self.w_max_urad_s:
            raise ValueError("GateParams: w_min_urad_s must be <= w_max_urad_s")
        if self.t_stale_us < 2 * self.lidar_period_us + self.dt_us:
            raise ValueError("GateParams: t_stale_us must be >= 2*lidar_period_us + dt_us")
        if 3 * self.proposer_period_us > self.t_watch_us:
            raise ValueError("GateParams: proposer_period_us must be <= t_watch_us/3")


# ----------------------------------------------------------------------------
# Inputs, state, outputs
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Proposal:
    """A velocity proposal from the untrusted proposer (already parsed by the shell)."""
    seq: int
    sim_stamp_us: int       # sim time of the gate snapshot the proposal was computed from
    left_urad_s: int
    right_urad_s: int
    session_id: int = 0     # process incarnation ID across restarts (F3 fix)


@dataclass(frozen=True)
class GateInputs:
    sim_time_us: int
    proposal: Optional[Proposal] = None            # newest candidate drained this tick (or None)
    ranges_m: Optional[Sequence[float]] = None     # forward-cone lidar ranges in metres
    lidar_stamp_us: Optional[int] = None           # sim time at which the scan was taken
    reset_source: Optional[str] = None             # None, "operator" or "proposer"
    log_write_failed: bool = False                 # shell reports a failed log write (R-10)
    raw_valid_points: Optional[int] = None         # count of valid finite returns across raw scan
    hsr_status: Optional[str] = None               # "CLEAR", "MONITOR", "CRITICAL", or None
    hsr_stamp_us: Optional[int] = None             # sim time at which HSR status was evaluated


@dataclass(frozen=True)
class GateState:
    mode: Mode = Mode.TRIPPED                      # fail-closed start
    last_tick_us: Optional[int] = None
    clear_since_us: Optional[int] = None
    held: Optional[Proposal] = None                # newest accepted proposal
    last_seq: int = -1                             # highest accepted sequence number
    last_cmd: Tuple[int, int] = (0, 0)
    last_session_id: int = -1                      # session ID of highest accepted proposal


@dataclass(frozen=True)
class StepResult:
    state: GateState
    cmd_left_urad_s: int
    cmd_right_urad_s: int
    reason: str
    events: Tuple[str, ...]
    record: dict                                    # log fields


def initial_state() -> GateState:
    return GateState()


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _ceil_div(a: int, b: int) -> int:
    return -((-a) // b)


def wheel_to_mmps(params: GateParams, w_urad_s: int) -> int:
    """Wheel angular speed (urad/s) -> linear speed (mm/s), rounded up. Never negative."""
    if w_urad_s <= 0:
        return 0
    return _ceil_div(w_urad_s * params.wheel_radius_mm, 1_000_000)


def d_stop_mm(params: GateParams, v_mmps: int) -> int:
    """d_stop = ceil(v^2 / (2*a_design)) + ceil(v * t_react / 1e6) + margin, in integer millimetres."""
    v = max(0, v_mmps)
    braking_mm = _ceil_div(v * v, 2 * params.a_design_mmps2)
    react_mm = _ceil_div(v * params.t_react_us, 1_000_000) if params.t_react_us > 0 else 0
    return braking_mm + react_mm + params.margin_mm


def clamp_to_envelope(params: GateParams, left: int, right: int) -> Tuple[int, int]:
    """AR-2 / R-05: clamp each wheel command into [w_min, w_max]."""
    lo, hi = params.w_min_urad_s, params.w_max_urad_s
    return (min(max(left, lo), hi), min(max(right, lo), hi))


def _validate_proposal(p) -> bool:
    if not isinstance(p, Proposal):
        return False
    for v in (p.seq, p.sim_stamp_us, p.left_urad_s, p.right_urad_s, p.session_id):
        if not _is_int(v):
            return False
    if p.seq < 0 or p.sim_stamp_us < 0 or p.session_id < 0:
        return False
    if abs(p.left_urad_s) > _WHEEL_SANITY_LIMIT or abs(p.right_urad_s) > _WHEEL_SANITY_LIMIT:
        return False
    return True


def _validate_lidar(params: GateParams, now: int, ranges_m, stamp_us, raw_valid_points: Optional[int] = None):
    """
    R-04 / D-6 / F1. Returns (ok, min_range_mm).
    min_range_mm is None when the scan is valid but contains no return (all +inf).
    """
    if ranges_m is None or stamp_us is None or not _is_int(stamp_us):
        return False, None
    if isinstance(ranges_m, (str, bytes)):
        return False, None
    try:
        n = len(ranges_m)
    except TypeError:
        return False, None
    if n != params.lidar_n_expected:
        return False, None
    age = now - stamp_us
    if age < 0 or age > params.t_stale_us:
        return False, None

    if raw_valid_points is not None:
        if not _is_int(raw_valid_points) or raw_valid_points < 0:
            return False, None

    smallest = math.inf
    finite_count = 0
    for x in ranges_m:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            return False, None
        if math.isnan(x) or x <= 0.0:
            return False, None
        if math.isfinite(x):
            finite_count += 1
            if x < smallest:
                smallest = x

    effective_raw = raw_valid_points if raw_valid_points is not None else finite_count
    if effective_raw < params.min_raw_lidar_returns:
        return False, None

    if math.isinf(smallest):
        return True, None
    return True, int(math.floor(smallest * 1000.0))


def _json_safe_val(x: Any) -> Any:
    """Converts NaNs, infinities, and arbitrary non-JSON types into compliant primitives."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return str(x)[:256]
    if math.isnan(x):
        return "nan"
    if math.isinf(x):
        return "+inf" if x > 0 else "-inf"
    return x


# ----------------------------------------------------------------------------
# The step function
# ----------------------------------------------------------------------------
def step(state: GateState, params: GateParams, inp: GateInputs) -> StepResult:
    """One gate evaluation. Pure: same (state, params, inp) always gives the same result."""
    now = inp.sim_time_us
    if not _is_int(now) or now < 0:
        raise TypeError(f"sim_time_us must be a non-negative int, got {now!r}")

    # strictly monotonic sim time (log requirement)
    if state.last_tick_us is not None and now <= state.last_tick_us:
        new_state = GateState(
            mode=Mode.TRIPPED, last_tick_us=now, clear_since_us=None,
            held=None, last_seq=state.last_seq, last_cmd=(0, 0),
            last_session_id=state.last_session_id,
        )
        record = _record(now, new_state.mode, Reason.TRIP_CLOCK_ANOMALY, (), None, None,
                         False, None, None, False, (0, 0), inp=inp)
        return StepResult(new_state, 0, 0, Reason.TRIP_CLOCK_ANOMALY, (), record)

    events = []

    # 1. proposal acceptance (R-06 semantic checks, F3 session restart handling)
    held, last_seq, last_session_id = state.held, state.last_seq, state.last_session_id
    cand = inp.proposal
    if cand is not None:
        if not _validate_proposal(cand):
            events.append(Event.MSG_REJECTED_INVALID)
        elif cand.sim_stamp_us > now:
            events.append(Event.MSG_REJECTED_FUTURE)
        elif cand.session_id < last_session_id:
            events.append(Event.MSG_REJECTED_SEQ)
        elif cand.session_id == last_session_id and cand.seq <= last_seq:
            events.append(Event.MSG_REJECTED_SEQ)
        else:
            held, last_seq, last_session_id = cand, cand.seq, cand.session_id

    # 2. clamp the newest accepted proposal into the envelope (AR-2, R-05)
    clamped = clamp_to_envelope(params, held.left_urad_s, held.right_urad_s) if held else (0, 0)

    # 3. speed bound and stop distance (F4 reaction-time inclusion)
    v_ref = max(
        wheel_to_mmps(params, max(state.last_cmd)),
        wheel_to_mmps(params, max(clamped)),
    )
    stop_mm = d_stop_mm(params, v_ref)

    # 4. lidar validity and obstacle hazard (R-01, R-04, AR-9, F1)
    lidar_ok, min_mm = _validate_lidar(params, now, inp.ranges_m, inp.lidar_stamp_us, inp.raw_valid_points)
    hazard = False
    if lidar_ok:
        hazard = min_mm is not None and min_mm <= stop_mm

    # 5. proposer freshness (R-02)
    age_us = None
    proposer_dead = held is None
    proposer_stale = False
    if held is not None:
        age_us = now - held.sim_stamp_us
        proposer_stale = age_us >= params.t_watch_us

    # 6. one primary trip reason, fixed priority
    hsr_age_us = None
    if inp.hsr_stamp_us is not None and _is_int(inp.hsr_stamp_us):
        hsr_age_us = now - inp.hsr_stamp_us

    trip_reason = None
    if inp.log_write_failed:
        trip_reason = Reason.TRIP_LOG_FAILURE
    elif not lidar_ok:
        trip_reason = Reason.TRIP_SENSOR_INVALID
    elif hazard:
        trip_reason = Reason.TRIP_OBSTACLE
    elif params.hsr_required and (
        inp.hsr_status is None or inp.hsr_status not in ("CLEAR", "MONITOR", "CRITICAL")
    ):
        trip_reason = Reason.TRIP_HSR_INVALID
    elif params.hsr_required and (
        inp.hsr_stamp_us is None or hsr_age_us is None or hsr_age_us < 0 or hsr_age_us > params.t_hsr_stale_us
    ):
        trip_reason = Reason.TRIP_HSR_STALE       # <--- Stale HSR Heartbeat Trip
    elif inp.hsr_status is not None and inp.hsr_status not in ("CLEAR", "MONITOR", "CRITICAL"):
        trip_reason = Reason.TRIP_HSR_INVALID
    elif inp.hsr_status == "CRITICAL":
        trip_reason = Reason.TRIP_HSR_CRITICAL
    elif proposer_dead:
        trip_reason = Reason.TRIP_PROPOSER_DEAD
    elif proposer_stale:
        trip_reason = Reason.TRIP_PROPOSER_STALE

    # 7. mode transitions
    mode = state.mode
    clear_since = state.clear_since_us
    cmd = (0, 0)

    if trip_reason is not None:
        mode, clear_since, reason = Mode.TRIPPED, None, trip_reason
    elif mode == Mode.RUN:
        reason, cmd = Reason.PASS, clamped
    else:
        gap_ok = state.last_tick_us is not None and (now - state.last_tick_us) <= params.max_tick_gap_us
        if mode == Mode.TRIPPED:
            if clear_since is None or not gap_ok:
                clear_since = now
            if now - clear_since >= params.t_dwell_us:
                mode = Mode.AWAITING_RESET
        reason = Reason.LATCHED_AWAIT_RESET if mode == Mode.AWAITING_RESET else Reason.LATCHED_DWELL

    # 8. reset handling (AR-4, R-07)
    if inp.reset_source is not None:
        if inp.reset_source != RESET_SOURCE_OPERATOR:
            events.append(Event.RESET_REJECTED_CHANNEL)
        elif (
            hazard
            or inp.hsr_status == "CRITICAL"
            or (params.hsr_required and inp.hsr_status != "CLEAR")
            or (inp.hsr_status is not None and inp.hsr_status != "CLEAR")
        ):
            events.append(Event.RESET_REJECTED_HAZARD)
        elif mode == Mode.AWAITING_RESET:
            mode, clear_since, reason = Mode.RUN, None, Reason.RESET_ACCEPTED
        elif mode == Mode.RUN:
            events.append(Event.RESET_IGNORED_RUN)
        else:
            events.append(Event.RESET_REJECTED_NOT_READY)

    new_state = GateState(
        mode=mode, last_tick_us=now, clear_since_us=clear_since,
        held=held, last_seq=last_seq, last_cmd=cmd,
        last_session_id=last_session_id,
    )
    record = _record(now, mode, reason, tuple(events), held, age_us, lidar_ok, min_mm,
                     stop_mm, hazard, cmd, inp=inp, hsr_age_us=hsr_age_us)
    return StepResult(new_state, cmd[0], cmd[1], reason, tuple(events), record)


def _record(now, mode, reason, events, held, age_us, lidar_ok, min_mm, stop_mm, hazard, cmd, inp: Optional[GateInputs] = None, hsr_age_us: Optional[int] = None) -> dict:
    rec = {
        "sim_time_us": now,
        "state": mode.value,
        "reason": reason,
        "events": list(events),
        "proposal_seq": None if held is None else held.seq,
        "proposal_age_us": age_us,
        "lidar_valid": lidar_ok,
        "lidar_min_mm": min_mm,
        "d_stop_mm": stop_mm,
        "obstacle_breach": hazard,
        "hsr_status": inp.hsr_status if inp is not None else None,
        "hsr_age_us": hsr_age_us,
        "cmd_left_urad_s": cmd[0],
        "cmd_right_urad_s": cmd[1],
    }
    if inp is not None:
        proposal_logged = None
        if isinstance(inp.proposal, Proposal):
            proposal_logged = {
                "seq": inp.proposal.seq,
                "sim_stamp_us": inp.proposal.sim_stamp_us,
                "left_urad_s": inp.proposal.left_urad_s,
                "right_urad_s": inp.proposal.right_urad_s,
                "session_id": inp.proposal.session_id,
            }
        elif inp.proposal is not None:
            proposal_logged = str(inp.proposal)[:256]

        ranges_logged = None
        if isinstance(inp.ranges_m, (list, tuple)):
            ranges_logged = [_json_safe_val(x) for x in inp.ranges_m]
        elif inp.ranges_m is not None:
            ranges_logged = _json_safe_val(inp.ranges_m)

        rec["inputs"] = {
            "raw_valid_points": inp.raw_valid_points,
            "lidar_stamp_us": inp.lidar_stamp_us,
            "reset_source": (
                inp.reset_source if isinstance(inp.reset_source, (str, type(None)))
                else str(inp.reset_source)[:64]
            ),
            "log_write_failed": bool(inp.log_write_failed),
            "proposal": proposal_logged,
            "ranges_m": ranges_logged,
            "hsr_status": (
                inp.hsr_status if isinstance(inp.hsr_status, (str, type(None)))
                else str(inp.hsr_status)[:64]
            ),
            "hsr_stamp_us": inp.hsr_stamp_us,
        }
    return rec
