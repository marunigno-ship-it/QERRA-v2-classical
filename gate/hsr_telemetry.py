"""
QERRA-v2 Classical — Layer 1B Telemetry Contract
Module: gate.hsr_telemetry
Version: 0.2.0 (Phase 2, Aligned with hsr/qerra_hsr.py)
License: Apache-2.0

Pure-standard-library telemetry contract, validation, and reduction functions
for asynchronous perception-to-Gate IPC.
Zero external dependencies. Eliminates IEEE-754 float epsilon at thresholds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final, Iterable, Mapping, Optional, Tuple, Union

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
    Returns True if an incoming packet repeats or regresses a frame counter,
    indicating a frozen upstream camera buffer or replay.
    """
    if last_seen_obs_id is None:
        return False
    return current_obs_id <= last_seen_obs_id


if __name__ == "__main__":
    print("[HSR TELEMETRY CONTRACT] Running inline verification against hsr/qerra_hsr.py rules...")

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

    # 7. Frozen frame detector
    assert not is_perception_frozen(current_obs_id=5, last_seen_obs_id=None)
    assert not is_perception_frozen(current_obs_id=6, last_seen_obs_id=5)
    assert is_perception_frozen(current_obs_id=5, last_seen_obs_id=5)
    assert is_perception_frozen(current_obs_id=4, last_seen_obs_id=5)

    print("[HSR TELEMETRY CONTRACT] All 7 assertion suites passed cleanly.")
