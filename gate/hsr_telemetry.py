"""
QERRA-v2 Classical — Layer 1B Telemetry Contract
Module: gate.hsr_telemetry
Version: 0.3.1 (Explicit Elapsed-Time Dwell Hardening)
License: Apache-2.0

Pure-standard-library telemetry contract, validation, reduction, and stream
freshness state machine for asynchronous perception-to-Gate IPC.
Zero external dependencies. Eliminates IEEE-754 float epsilon at thresholds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final, Iterable, Mapping, Optional, Sequence, Tuple, Union

# Reflex state strings matching gate_core.py v0.4 and hsr/qerra_hsr.py
HSR_CLEAR: Final[str] = "CLEAR"
HSR_MONITOR: Final[str] = "MONITOR"
HSR_CRITICAL: Final[str] = "CRITICAL"

VALID_STATES: Final[Tuple[str, ...]] = (HSR_CLEAR, HSR_MONITOR, HSR_CRITICAL)

# Severity total order: CLEAR (0) < MONITOR (1) < CRITICAL (2)
SEVERITY_ORDER: Final[Mapping[str, int]] = {
    HSR_CLEAR: 0,
    HSR_MONITOR: 1,
    HSR_CRITICAL: 2,
}

# Ground-truth thresholds from hsr/qerra_hsr.py mapped to integer permille [0, 1000]
DEFAULT_MONITOR_THRESHOLD_PERMILLE: Final[int] = 450   # DISTRESS_MONITOR_THRESHOLD = 0.45
DEFAULT_CRITICAL_THRESHOLD_PERMILLE: Final[int] = 750  # DISTRESS_CRITICAL_THRESHOLD = 0.75
ISOLATION_COUNT_THRESHOLD: Final[int] = 1              # ISOLATION_COUNT_THRESHOLD = 1


def classify_hsr_telemetry(
    distress_permille: int,
    hazard_proximity: bool = False,
    persons_nearby_count: int = 2,
    monitor_threshold: int = DEFAULT_MONITOR_THRESHOLD_PERMILLE,
    critical_threshold: int = DEFAULT_CRITICAL_THRESHOLD_PERMILLE,
) -> str:
    """
    Pure classifier mapping integer permille and social context to HSR reflex state.
    Strictly mirrors evaluate_hsr() in hsr/qerra_hsr.py without floating-point math.
    """
    if not isinstance(distress_permille, int) or isinstance(distress_permille, bool):
        raise ValueError(f"distress_permille must be integer, got {distress_permille!r}")
    if not (0 <= distress_permille <= 1000):
        raise ValueError(f"distress_permille must be in [0, 1000], got {distress_permille}")

    if not isinstance(hazard_proximity, bool):
        raise ValueError(f"hazard_proximity must be bool, got {hazard_proximity!r}")

    if not isinstance(persons_nearby_count, int) or isinstance(persons_nearby_count, bool):
        raise ValueError(f"persons_nearby_count must be integer, got {persons_nearby_count!r}")
    if persons_nearby_count < 0:
        raise ValueError(f"persons_nearby_count cannot be negative, got {persons_nearby_count}")

    distress_critical = distress_permille >= critical_threshold
    distress_monitor = distress_permille >= monitor_threshold
    person_isolated = persons_nearby_count <= ISOLATION_COUNT_THRESHOLD
    distress_isolated_combined = distress_monitor and person_isolated

    # Fail-closed escalation matching Layer 1B rules
    if distress_critical or hazard_proximity or distress_isolated_combined:
        return HSR_CRITICAL
    if distress_monitor:
        return HSR_MONITOR
    return HSR_CLEAR


@dataclass(frozen=True)
class HSRTelemetryPacket:
    """
    Immutable validated perception record received at the Gate interface.

    Attributes:
        obs_id: Monotonic frame counter from perception sensor (detects frozen frames).
        t_obs_us: Capture timestamp of sensor frame (sim time microseconds).
        t_emit_us: Transmission timestamp after inference serialization (sim time microseconds).
        t_rx_us: Gate local timestamp at non-blocking socket drain (sim time microseconds).
        distress_permille: Scaled distress reading in [0, 1000].
        state: Derived or validated reflex state (CLEAR, MONITOR, CRITICAL).
        hazard_proximity: Environmental hazard flag (ISO 13482 physical hazard).
        persons_nearby_count: Count of responsive humans nearby (isolation vector).
    """
    obs_id: int
    t_obs_us: int
    t_emit_us: int
    t_rx_us: int
    distress_permille: int
    state: str
    hazard_proximity: bool = False
    persons_nearby_count: int = 2

    def severity(self) -> int:
        """Returns integer severity: CLEAR=0, MONITOR=1, CRITICAL=2."""
        return SEVERITY_ORDER[self.state]


def parse_hsr_telemetry(
    raw_payload: Union[str, bytes],
    t_rx_us: int,
    monitor_threshold: int = DEFAULT_MONITOR_THRESHOLD_PERMILLE,
    critical_threshold: int = DEFAULT_CRITICAL_THRESHOLD_PERMILLE,
) -> HSRTelemetryPacket:
    """
    Parse and strictly validate a wire payload (JSON string or bytes).

    Invariants enforced:
      1. obs_id >= 0
      2. 0 <= t_obs_us <= t_emit_us
      3. t_obs_us <= t_rx_us (rejects future timestamps fail-closed)
      4. 0 <= distress_permille <= 1000 (strictly integer)
      5. Optional hazard_proximity must be boolean.
      6. Optional persons_nearby_count must be integer >= 0.
      7. If 'state' is explicitly declared, it must match ground-truth classification.
    """
    if isinstance(raw_payload, bytes):
        raw_payload = raw_payload.decode("utf-8")

    data = json.loads(raw_payload)
    if not isinstance(data, dict):
        raise ValueError(f"Payload must be a JSON object, got {type(data).__name__}")

    required = ("obs_id", "t_obs_us", "t_emit_us", "distress_permille")
    for field in required:
        if field not in data:
            raise ValueError(f"Missing required HSR telemetry field: '{field}'")
        val = data[field]
        if not isinstance(val, int) or isinstance(val, bool):
            raise ValueError(f"Field '{field}' must be integer, got {val!r}")

    obs_id = data["obs_id"]
    t_obs_us = data["t_obs_us"]
    t_emit_us = data["t_emit_us"]
    distress_permille = data["distress_permille"]
    t_rx = int(t_rx_us)

    if obs_id < 0:
        raise ValueError(f"obs_id must be non-negative, got {obs_id}")
    if t_obs_us < 0:
        raise ValueError(f"t_obs_us must be non-negative, got {t_obs_us}")
    if t_emit_us < t_obs_us:
        raise ValueError(f"Causal inversion: t_emit_us ({t_emit_us}) < t_obs_us ({t_obs_us})")
    if t_rx < t_obs_us:
        raise ValueError(f"Clock inversion / future frame: t_rx_us ({t_rx}) < t_obs_us ({t_obs_us})")
    if not (0 <= distress_permille <= 1000):
        raise ValueError(f"distress_permille out of range [0, 1000]: {distress_permille}")

    hazard_proximity = data.get("hazard_proximity", False)
    if not isinstance(hazard_proximity, bool):
        raise ValueError(f"hazard_proximity must be bool, got {hazard_proximity!r}")

    persons_nearby_count = data.get("persons_nearby_count", 2)
    if not isinstance(persons_nearby_count, int) or isinstance(persons_nearby_count, bool) or persons_nearby_count < 0:
        raise ValueError(f"persons_nearby_count must be non-negative int, got {persons_nearby_count!r}")

    derived_state = classify_hsr_telemetry(
        distress_permille=distress_permille,
        hazard_proximity=hazard_proximity,
        persons_nearby_count=persons_nearby_count,
        monitor_threshold=monitor_threshold,
        critical_threshold=critical_threshold,
    )

    if "state" in data:
        declared_state = str(data["state"]).strip()
        if declared_state not in VALID_STATES:
            raise ValueError(f"Invalid declared state: '{declared_state}'")
        if declared_state != derived_state:
            raise ValueError(
                f"State mismatch: declared '{declared_state}' != derived '{derived_state}'"
            )

    return HSRTelemetryPacket(
        obs_id=obs_id,
        t_obs_us=t_obs_us,
        t_emit_us=t_emit_us,
        t_rx_us=t_rx,
        distress_permille=distress_permille,
        state=derived_state,
        hazard_proximity=hazard_proximity,
        persons_nearby_count=persons_nearby_count,
    )


def drain_worst_severity(
    packets: Iterable[HSRTelemetryPacket],
) -> Optional[HSRTelemetryPacket]:
    """
    Fold over a batch of packets drained in a single Gate evaluation cycle.

    Enforces the 'Worst-Severity-Wins' safety invariant:
    1. Highest severity level strictly dominates (CRITICAL > MONITOR > CLEAR).
    2. Among packets with equal worst severity, the freshest observation
       (highest t_obs_us, break ties with highest obs_id) wins.

    Returns None if packets iterable is empty.
    """
    worst_packet: Optional[HSRTelemetryPacket] = None
    worst_key: Tuple[int, int, int] = (-1, -1, -1)

    for p in packets:
        current_key = (p.severity(), p.t_obs_us, p.obs_id)
        if current_key > worst_key:
            worst_key = current_key
            worst_packet = p

    return worst_packet


def is_perception_frozen(
    current_obs_id: int,
    last_seen_obs_id: Optional[int],
) -> bool:
    """
    Pure predicate. Returns True if an incoming packet repeats or regresses a
    frame counter, indicating a frozen upstream camera buffer or replay.
    """
    if last_seen_obs_id is None:
        return False
    return current_obs_id <= last_seen_obs_id


# ----------------------------------------------------------------------------
# Layer 1B Pure Stream Monitor & Controlled Rebase State Machine
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class HSRStreamState:
    """
    Immutable state of the Layer 1B perception freshness monitor.

    Attributes:
        last_seen_obs_id: Highest sequence counter accepted in nominal operation.
        last_seen_t_obs_us: Capture timestamp of the last accepted observation.
        frozen_latched: True if an identical frame counter was observed (sticky freeze).
        rebase_in_progress: True if a counter regression / producer restart was detected.
        rebase_streak: Consecutive control ticks observing fresh, strictly advancing CLEAR frames.
        rebase_start_t_obs_us: Sensor timestamp of first clean CLEAR frame in current dwell.
        last_valid_status: Most recent valid reflex state (held across nominal idle ticks).
        last_valid_stamp_us: Most recent observation timestamp (held across nominal idle ticks).
    """
    last_seen_obs_id: Optional[int] = None
    last_seen_t_obs_us: Optional[int] = None
    frozen_latched: bool = False
    rebase_in_progress: bool = False
    rebase_streak: int = 0
    rebase_start_t_obs_us: Optional[int] = None
    last_valid_status: Optional[str] = None
    last_valid_stamp_us: Optional[int] = None


def step_hsr_stream(
    state: HSRStreamState,
    packets: Sequence[HSRTelemetryPacket],
    now_us: int,
    *,
    max_age_us: int = 96_000,
    required_streak: int = 5,
    required_dwell_us: int = 160_000,
) -> Tuple[HSRStreamState, Optional[str], Optional[int]]:
    """
    Pure deterministic control-cycle step for Layer 1B HSR stream monitoring.

    Enforces functional-safety requirements:
      1. Per-packet sequence inspection BEFORE batch reduction (closes Trap 2).
      2. Sticky frozen-frame latching (closes Trap 1).
      3. Controlled producer restart recovery requiring dual-gate criteria:
         - At least `required_streak` (default 5) consecutive control ticks.
         - At least `required_dwell_us` (default 160,000 µs = 160 ms) of elapsed
           sensor observation time (closes fencepost interval gap).
      4. At most +1 streak credit per tick (closes 1 ms burst trap).
      5. Any distress (MONITOR/CRITICAL), regression, or freeze during dwell resets streak and start timer.
      6. While latched or in rebase, output status is None (trips TRIP_HSR_INVALID in gate_core).

    Returns:
      (new_state, hsr_status, hsr_stamp_us)
    """
    last_obs = state.last_seen_obs_id
    last_t_obs = state.last_seen_t_obs_us
    frozen = state.frozen_latched
    rebase = state.rebase_in_progress
    streak = state.rebase_streak
    start_t_obs = state.rebase_start_t_obs_us
    held_status = state.last_valid_status
    held_stamp = state.last_valid_stamp_us

    # 1. Per-packet inspection in strict arrival order across the batch
    batch_has_freeze = False
    batch_has_regression = False
    batch_has_distress = False
    batch_has_stale = False
    current_eval_obs = last_obs
    current_eval_t = last_t_obs

    for p in packets:
        # Freshness bound against current gate clock
        age_us = now_us - p.t_obs_us
        if age_us < 0 or age_us > max_age_us:
            batch_has_stale = True

        if p.state in (HSR_MONITOR, HSR_CRITICAL):
            batch_has_distress = True

        if current_eval_obs is not None:
            if p.obs_id == current_eval_obs:
                batch_has_freeze = True
            elif p.obs_id < current_eval_obs or (current_eval_t is not None and p.t_obs_us < current_eval_t):
                batch_has_regression = True

        current_eval_obs = p.obs_id
        current_eval_t = p.t_obs_us

    # 2. Update latches based on batch inspection
    if batch_has_freeze:
        frozen = True

    if batch_has_regression:
        rebase = True
        streak = 0
        start_t_obs = None

    # 3. Controlled Rebase & Sticky Fault Evaluation
    if frozen or rebase:
        if len(packets) == 0:
            # Idle tick during fault: streak and elapsed time hold (idle ticks cannot satisfy dwell)
            pass
        elif batch_has_freeze or batch_has_regression or batch_has_distress or batch_has_stale:
            # Any non-compliant frame during dwell wipes streak and dwell start timestamp
            streak = 0
            start_t_obs = None
            last_obs = current_eval_obs
            last_t_obs = current_eval_t
        else:
            # Tick delivered fresh, strictly advancing CLEAR frames
            streak += 1
            if start_t_obs is None:
                # Latch the timestamp of the first frame that initiated the unbroken clean sequence
                start_t_obs = packets[0].t_obs_us

            last_obs = current_eval_obs
            last_t_obs = current_eval_t

            elapsed_us = (current_eval_t - start_t_obs) if (current_eval_t is not None and start_t_obs is not None) else 0

            # Dual-gate completion: must satisfy both tick count AND elapsed physical duration
            if streak >= required_streak and elapsed_us >= required_dwell_us:
                frozen = False
                rebase = False
                streak = 0
                start_t_obs = None
                held_status = HSR_CLEAR
                held_stamp = current_eval_t

        if frozen or rebase:
            # Still in fault or rebase dwell: output None (forces TRIP_HSR_INVALID in gate_core)
            new_state = HSRStreamState(
                last_seen_obs_id=last_obs,
                last_seen_t_obs_us=last_t_obs,
                frozen_latched=frozen,
                rebase_in_progress=rebase,
                rebase_streak=streak,
                rebase_start_t_obs_us=start_t_obs,
                last_valid_status=None,
                last_valid_stamp_us=None,
            )
            return new_state, None, None

    # 4. Nominal Operation
    if len(packets) > 0:
        winning = drain_worst_severity(packets)
        assert winning is not None
        held_status = winning.state
        held_stamp = winning.t_obs_us
        last_obs = current_eval_obs
        last_t_obs = current_eval_t

    new_state = HSRStreamState(
        last_seen_obs_id=last_obs,
        last_seen_t_obs_us=last_t_obs,
        frozen_latched=False,
        rebase_in_progress=False,
        rebase_streak=0,
        rebase_start_t_obs_us=None,
        last_valid_status=held_status,
        last_valid_stamp_us=held_stamp,
    )
    return new_state, held_status, held_stamp


# ----------------------------------------------------------------------------
# Inline Verification Suite
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    print("[HSR TELEMETRY CONTRACT] Running inline verification suites...")

    # 1. Exact permille boundary verification (0.45 and 0.75)
    assert classify_hsr_telemetry(0) == HSR_CLEAR
    assert classify_hsr_telemetry(449) == HSR_CLEAR
    assert classify_hsr_telemetry(450) == HSR_MONITOR
    assert classify_hsr_telemetry(749) == HSR_MONITOR
    assert classify_hsr_telemetry(750) == HSR_CRITICAL
    assert classify_hsr_telemetry(1000) == HSR_CRITICAL

    # 2. Compound escalation (distress_monitor + isolated person count <= 1)
    assert classify_hsr_telemetry(450, persons_nearby_count=2) == HSR_MONITOR
    assert classify_hsr_telemetry(450, persons_nearby_count=1) == HSR_CRITICAL
    assert classify_hsr_telemetry(450, persons_nearby_count=0) == HSR_CRITICAL

    # 3. Environmental hazard proximity flag
    assert classify_hsr_telemetry(0, hazard_proximity=True) == HSR_CRITICAL

    # 4. Wire parsing with valid payload
    valid_payload = json.dumps({
        "obs_id": 101,
        "t_obs_us": 32000,
        "t_emit_us": 33000,
        "distress_permille": 750,
        "state": "CRITICAL",
    })
    pkt = parse_hsr_telemetry(valid_payload, t_rx_us=34000)
    assert pkt.obs_id == 101
    assert pkt.state == HSR_CRITICAL
    assert pkt.severity() == 2

    # 5. Causal and future timestamp failure checks
    try:
        bad_emit = json.dumps({"obs_id": 1, "t_obs_us": 200, "t_emit_us": 100, "distress_permille": 0})
        parse_hsr_telemetry(bad_emit, t_rx_us=300)
        assert False, "Should fail on t_emit < t_obs"
    except ValueError:
        pass

    try:
        future_frame = json.dumps({"obs_id": 1, "t_obs_us": 500, "t_emit_us": 550, "distress_permille": 0})
        parse_hsr_telemetry(future_frame, t_rx_us=400)
        assert False, "Should fail on t_rx < t_obs"
    except ValueError:
        pass

    # 6. Worst-severity drain reduction
    p_clear = HSRTelemetryPacket(10, 1000, 1100, 1500, 100, HSR_CLEAR)
    p_crit_early = HSRTelemetryPacket(11, 1050, 1150, 1500, 800, HSR_CRITICAL)
    p_clear_late = HSRTelemetryPacket(12, 1100, 1200, 1500, 50, HSR_CLEAR)

    batch = [p_clear, p_crit_early, p_clear_late]
    winning = drain_worst_severity(batch)
    assert winning is not None
    assert winning.obs_id == 11
    assert winning.state == HSR_CRITICAL

    # 7. Pure predicate frozen frame detector
    assert not is_perception_frozen(current_obs_id=5, last_seen_obs_id=None)
    assert not is_perception_frozen(current_obs_id=6, last_seen_obs_id=5)
    assert is_perception_frozen(current_obs_id=5, last_seen_obs_id=5)
    assert is_perception_frozen(current_obs_id=4, last_seen_obs_id=5)

    # 8. Hardened Stream Monitor (step_hsr_stream) verification
    s0 = HSRStreamState()
    # Nominal initial tick
    p1 = HSRTelemetryPacket(1, 100_000, 101_000, 102_000, 0, HSR_CLEAR)
    s1, st, stamp = step_hsr_stream(s0, [p1], now_us=102_000)
    assert st == HSR_CLEAR and stamp == 100_000
    assert s1.last_seen_obs_id == 1 and not s1.frozen_latched

    # Idle tick holds nominal status
    s2, st, stamp = step_hsr_stream(s1, [], now_us=134_000)
    assert st == HSR_CLEAR and stamp == 100_000

    # Frozen frame detection (repeated obs_id=1) -> Trips sticky fault
    p_frozen = HSRTelemetryPacket(1, 166_000, 167_000, 168_000, 0, HSR_CLEAR)
    s3, st, stamp = step_hsr_stream(s2, [p_frozen], now_us=168_000)
    assert s3.frozen_latched is True
    assert st is None and stamp is None, "Frozen frame must immediately clear status to trip gate"

    # Subsequent idle tick during fault remains sticky None
    s4, st, stamp = step_hsr_stream(s3, [], now_us=200_000)
    assert st is None and stamp is None

    # Within-batch duplicate / freeze (Trap 2: p_a has obs_id=5, p_b has obs_id=5)
    s_clean = HSRStreamState(last_seen_obs_id=4, last_seen_t_obs_us=100_000)
    p_dup_a = HSRTelemetryPacket(5, 200_000, 201_000, 202_000, 0, HSR_CLEAR)
    p_dup_b = HSRTelemetryPacket(5, 200_100, 201_100, 202_000, 0, HSR_CLEAR)
    s_trap2, st, stamp = step_hsr_stream(s_clean, [p_dup_a, p_dup_b], now_us=202_000)
    assert s_trap2.frozen_latched is True
    assert st is None, "Within-batch duplicate must trip frozen latch"

    # Producer Restart & Dual-Gate Dwell Verification (streak >= 5 AND elapsed >= 160 ms)
    s_high = HSRStreamState(last_seen_obs_id=5000, last_seen_t_obs_us=1_000_000)
    # Restart datagram: obs_id drops to 0
    p_restart = HSRTelemetryPacket(0, 1_032_000, 1_033_000, 1_034_000, 0, HSR_CLEAR)
    s_re, st, _ = step_hsr_stream(s_high, [p_restart], now_us=1_034_000)
    assert s_re.rebase_in_progress is True
    assert s_re.rebase_streak == 0
    assert s_re.rebase_start_t_obs_us is None
    assert st is None

    # Tick 1: Burst of 3 packets in 1 tick only credits +1 tick streak, establishes start_t_obs = 1,064,000 (first packet)
    p_b1 = HSRTelemetryPacket(1, 1_064_000, 1_065_000, 1_066_000, 0, HSR_CLEAR)
    p_b2 = HSRTelemetryPacket(2, 1_064_100, 1_065_100, 1_066_000, 0, HSR_CLEAR)
    p_b3 = HSRTelemetryPacket(3, 1_064_200, 1_065_200, 1_066_000, 0, HSR_CLEAR)
    s_re, st, _ = step_hsr_stream(s_re, [p_b1, p_b2, p_b3], now_us=1_066_000)
    assert s_re.rebase_streak == 1
    assert s_re.rebase_start_t_obs_us == 1_064_000
    assert st is None

    # Ticks 2, 3, 4 with advancing CLEAR packets
    for i in range(2, 5):
        pkt_i = HSRTelemetryPacket(3 + i, 1_064_000 + i * 32_000, 1_065_000 + i * 32_000, 1_066_000 + i * 32_000, 0, HSR_CLEAR)
        s_re, st, _ = step_hsr_stream(s_re, [pkt_i], now_us=1_066_000 + i * 32_000)
        assert s_re.rebase_streak == i
        assert st is None

    # Boundary test: at 159 ms elapsed (t_obs = 1_064_000 + 159_000 = 1_223_000), dwell must NOT complete
    pkt_boundary = HSRTelemetryPacket(8, 1_223_000, 1_224_000, 1_225_000, 0, HSR_CLEAR)
    s_boundary, st_b, _ = step_hsr_stream(s_re, [pkt_boundary], now_us=1_225_000)
    assert s_boundary.rebase_in_progress is True, "At 159 ms elapsed, dwell must not complete"
    assert st_b is None

    # Exact threshold: at 160 ms elapsed (t_obs = 1_064_000 + 160_000 = 1_224_000), dwell completes!
    pkt_fin = HSRTelemetryPacket(9, 1_224_000, 1_225_000, 1_226_000, 0, HSR_CLEAR)
    s_fin, st_fin, stamp_fin = step_hsr_stream(s_re, [pkt_fin], now_us=1_226_000)
    assert s_fin.rebase_in_progress is False
    assert s_fin.rebase_streak == 0
    assert s_fin.rebase_start_t_obs_us is None
    assert st_fin == HSR_CLEAR and stamp_fin == 1_224_000, "160 ms elapsed dwell must complete rebase and emit CLEAR"

    print("[HSR TELEMETRY CONTRACT] All 8 assertion suites PASSED cleanly.")
