# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Exhaustive Invariant and Property-Based Fuzzing for QERRA Layer 1A and Layer 1B.

Asserts mathematical safety invariants across boundary matrices,
100,000 gate core transitions, and 10,000 HSR telemetry stream transitions.
Pure Python stdlib + pytest only.
"""
import math
import random
from typing import Optional, Sequence

import pytest

from gate.gate_core import (
    Event,
    GateInputs,
    GateParams,
    GateState,
    Mode,
    Proposal,
    Reason,
    RESET_SOURCE_OPERATOR,
    RESET_SOURCE_PROPOSER,
    chassis_forward_mmps,
    d_stop_mm,
    initial_state,
    is_at_standstill,
    step,
)
from gate.hsr_telemetry import (
    HSR_CLEAR,
    HSR_CRITICAL,
    HSR_MONITOR,
    HSRStreamState,
    HSRTelemetryPacket,
    classify_hsr_telemetry,
    drain_worst_severity,
    step_hsr_stream,
)

FUZZ_SEED = 0x5EED_2026


# ----------------------------------------------------------------------------
# 1. Zero Actuator Authority Invariant
# ----------------------------------------------------------------------------
class TestActuatorZeroAuthorityInvariant:
    """Proves that in non-RUN modes, wheel commands are strictly (0, 0)."""

    @pytest.mark.parametrize("mode", [Mode.TRIPPED, Mode.AWAITING_RESET])
    @pytest.mark.parametrize("req_speed", [100_000, 1_000_000, 3_000_000, 50_000_000])
    @pytest.mark.parametrize("reset_src", [None, RESET_SOURCE_PROPOSER, "attacker", "operator_invalid"])
    def test_zero_actuator_authority_under_any_proposal_or_bad_reset(
        self, mode: Mode, req_speed: int, reset_src: Optional[str]
    ):
        params = GateParams(lidar_n_expected=5)
        state = GateState(mode=mode, last_tick_us=1_000_000)
        prop = Proposal(seq=1, sim_stamp_us=1_032_000, left_urad_s=req_speed, right_urad_s=req_speed)

        inp = GateInputs(
            sim_time_us=1_032_000,
            proposal=prop,
            ranges_m=[2.0, 2.0, 2.0, 2.0, 2.0],
            lidar_stamp_us=1_032_000,
            reset_source=reset_src,
        )
        res = step(state, params, inp)

        # Unless an operator successfully transitions AWAITING_RESET to RUN,
        # non-RUN modes MUST produce exactly (0, 0).
        if res.state.mode in (Mode.TRIPPED, Mode.AWAITING_RESET):
            assert res.cmd_left_urad_s == 0, f"Authority leak: left cmd {res.cmd_left_urad_s}"
            assert res.cmd_right_urad_s == 0, f"Authority leak: right cmd {res.cmd_right_urad_s}"


# ----------------------------------------------------------------------------
# 2. Dynamic Stopping Envelope Invariant
# ----------------------------------------------------------------------------
class TestStoppingEnvelopeInvariants:
    """Proves d_stop_mm bounds and rotation isolation."""

    def test_d_stop_lower_bound_always_greater_or_equal_margin(self):
        params = GateParams(lidar_n_expected=5, margin_mm=300)
        rng = random.Random(FUZZ_SEED)

        for _ in range(5_000):
            v_cmd = rng.randint(-1_000_000, 5_000_000)
            v_meas = rng.randint(-1_000_000, 5_000_000)
            v_ref = max(0, v_cmd, v_meas)
            stop_dist = d_stop_mm(params, v_ref)
            assert stop_dist >= params.margin_mm, f"d_stop {stop_dist} violated margin {params.margin_mm}"

    def test_in_place_yaw_spin_does_not_inflate_envelope(self):
        params = GateParams(lidar_n_expected=5, margin_mm=300)
        # Test pure differential rotation across 100 opposing wheel speeds
        for spin_speed in range(0, 3_000_000, 30_000):
            fwd_speed = chassis_forward_mmps(params, spin_speed, -spin_speed)
            assert fwd_speed == 0
            assert d_stop_mm(params, fwd_speed) == params.margin_mm


# ----------------------------------------------------------------------------
# 3. Clock Monotonicity Invariant
# ----------------------------------------------------------------------------
class TestClockMonotonicityInvariant:
    """Proves backward jumps and non-increasing timestamps fail closed immediately."""

    @pytest.mark.parametrize("delta_us", [0, -1, -32_000, -1_000_000, -999_999_999])
    @pytest.mark.parametrize("initial_mode", [Mode.RUN, Mode.TRIPPED, Mode.AWAITING_RESET])
    def test_non_increasing_clock_trips_immediately(self, delta_us: int, initial_mode: Mode):
        params = GateParams(lidar_n_expected=5)
        last_tick = 10_000_000
        state = GateState(mode=initial_mode, last_tick_us=last_tick, last_cmd=(500_000, 500_000))

        inp = GateInputs(
            sim_time_us=max(0, last_tick + delta_us),
            ranges_m=[3.0, 3.0, 3.0, 3.0, 3.0],
            lidar_stamp_us=max(0, last_tick + delta_us),
        )
        res = step(state, params, inp)

        assert res.state.mode == Mode.TRIPPED
        assert res.reason == Reason.TRIP_CLOCK_ANOMALY
        assert res.cmd_left_urad_s == 0
        assert res.cmd_right_urad_s == 0
        assert res.state.clear_since_us is None
        assert res.state.hsr_clear_since_us is None


# ----------------------------------------------------------------------------
# 4. Standstill & Dwell Qualification Invariant
# ----------------------------------------------------------------------------
class TestStandstillAndDwellInvariants:
    """Proves TRIPPED cannot transition to AWAITING_RESET while moving."""

    def test_dwell_cannot_complete_without_confirmed_standstill(self):
        params = GateParams(lidar_n_expected=5, standstill_required=True, t_dwell_us=1_000_000)
        state = GateState(mode=Mode.TRIPPED, last_tick_us=1_000_000, clear_since_us=1_000_000)

        # 2 seconds have passed (dwell would have elapsed), but robot is coasting at 200,000 urad/s
        inp = GateInputs(
            sim_time_us=3_000_000,
            ranges_m=[3.0, 3.0, 3.0, 3.0, 3.0],
            lidar_stamp_us=3_000_000,
            proposal=Proposal(seq=10, sim_stamp_us=3_000_000, left_urad_s=0, right_urad_s=0),
            meas_left_urad_s=200_000,
            meas_right_urad_s=200_000,
        )
        res = step(state, params, inp)

        # Must remain in TRIPPED, clear_since reset to None, command strictly 0
        assert res.state.mode == Mode.TRIPPED
        assert res.state.clear_since_us is None
        assert res.reason == Reason.LATCHED_DWELL
        assert res.cmd_left_urad_s == 0


# ----------------------------------------------------------------------------
# 5. Layer 1A: Exhaustive Multi-Tick Fuzzing (100,000 Transitions)
# ----------------------------------------------------------------------------
class TestExhaustiveStateSpaceFuzzing:
    """
    Executes 100,000 consecutive randomized state transitions across
    nominal, degraded, and adversarial inputs.
    """

    def test_100k_state_transitions_invariant_matrix(self):
        rng = random.Random(FUZZ_SEED)
        params = GateParams(
            lidar_n_expected=5,
            standstill_required=True,
            hsr_required=False,
            margin_mm=300,
            w_max_urad_s=3_000_000,
        )

        state = initial_state()
        sim_time_us = 1_000_000

        # Pre-allocated candidate range scenarios for high throughput
        ranges_candidates = [
            [2.5, 2.5, 2.5, 2.5, 2.5],            # clear forward
            [0.2, 0.2, 0.2, 0.2, 0.2],            # hazard (200mm)
            [math.inf, math.inf, math.inf, math.inf, math.inf],  # empty scan
            [2.5, math.nan, 2.5, 2.5, 2.5],       # invalid scan (NaN)
            [2.5, -0.1, 2.5, 2.5, 2.5],           # invalid scan (negative)
            None,                                  # missing scan
        ]
        reset_candidates = [None, None, None, None, RESET_SOURCE_OPERATOR, RESET_SOURCE_PROPOSER, "invalid_src"]
        hsr_candidates = [None, "CLEAR", "MONITOR", "CRITICAL", "CORRUPTED"]

        for tick in range(100_000):
            # Clock: 99.8% monotonic step (32ms), 0.2% backward jump
            if rng.random() < 0.002:
                sim_time_us = max(0, sim_time_us - rng.randint(1, 100_000))
            else:
                sim_time_us += 32_000

            # Telemetry & Proposer fuzzing
            meas_l = rng.choice([None, 0, rng.randint(-100_000, 3_500_000)])
            meas_r = rng.choice([None, 0, rng.randint(-100_000, 3_500_000)])

            has_prop = rng.random() > 0.10
            prop = None
            if has_prop:
                prop = Proposal(
                    seq=tick,
                    sim_stamp_us=sim_time_us - rng.randint(0, 100_000),
                    left_urad_s=rng.randint(-500_000, 4_000_000),
                    right_urad_s=rng.randint(-500_000, 4_000_000),
                    session_id=0,
                )

            inp = GateInputs(
                sim_time_us=sim_time_us,
                proposal=prop,
                ranges_m=rng.choice(ranges_candidates),
                lidar_stamp_us=sim_time_us - rng.choice([0, 10_000, 200_000]),
                reset_source=rng.choice(reset_candidates),
                log_write_failed=(rng.random() < 0.001),
                raw_valid_points=rng.choice([None, 0, 3, 10]),
                hsr_status=rng.choice(hsr_candidates),
                hsr_stamp_us=sim_time_us,
                proposal_invalid=(rng.random() < 0.005),
                meas_left_urad_s=meas_l,
                meas_right_urad_s=meas_r,
            )

            # Step evaluation
            res = step(state, params, inp)

            # --- HARD SAFETY INVARIANTS ---
            # Invariant 1: Non-RUN modes never command motion
            if res.state.mode in (Mode.TRIPPED, Mode.AWAITING_RESET):
                assert res.cmd_left_urad_s == 0, f"Tick {tick}: Actuator leak in {res.state.mode}"
                assert res.cmd_right_urad_s == 0, f"Tick {tick}: Actuator leak in {res.state.mode}"

            # Invariant 2: Wheel commands strictly within [w_min, w_max]
            assert params.w_min_urad_s <= res.cmd_left_urad_s <= params.w_max_urad_s, f"Tick {tick}: Left out of bounds"
            assert params.w_min_urad_s <= res.cmd_right_urad_s <= params.w_max_urad_s, f"Tick {tick}: Right out of bounds"

            # Invariant 3: Stopping envelope never collapses below margin (unless clock anomaly bypassed evaluation)
            if res.reason == Reason.TRIP_CLOCK_ANOMALY:
                assert res.record["d_stop_mm"] is None, f"Tick {tick}: Clock anomaly must log d_stop_mm as None"
            else:
                assert res.record["d_stop_mm"] is not None, f"Tick {tick}: Normal tick missing d_stop_mm"
                assert res.record["d_stop_mm"] >= params.margin_mm, f"Tick {tick}: Stopping envelope collapsed"

            # Invariant 4: Standstill violation defense
            moving = not is_at_standstill(params, inp.meas_left_urad_s, inp.meas_right_urad_s)
            if res.state.mode == Mode.TRIPPED and moving:
                assert res.state.clear_since_us is None, f"Tick {tick}: clear_since leaked during motion"

            state = res.state


# ----------------------------------------------------------------------------
# 6. Layer 1B: HSR Classifier Mathematical Invariants
# ----------------------------------------------------------------------------
class TestHSRClassifierInvariants:
    """Proves classification correctness across the entire permille state space."""

    def test_full_permille_space_monotonicity(self):
        """Tests all 1,001 integer permille values under nominal social context."""
        for p in range(1001):
            c = classify_hsr_telemetry(p, hazard_proximity=False, persons_nearby_count=2)
            if p >= 750:
                assert c == HSR_CRITICAL
            elif p >= 450:
                assert c == HSR_MONITOR
            else:
                assert c == HSR_CLEAR

    def test_hazard_proximity_always_critical(self):
        """Environmental hazard must strictly force CRITICAL across all permille and counts."""
        for p in range(0, 1001, 50):
            for count in (0, 1, 2, 5):
                assert classify_hsr_telemetry(p, hazard_proximity=True, persons_nearby_count=count) == HSR_CRITICAL

    def test_social_isolation_escalation(self):
        """Count <= 1 must escalate MONITOR (>= 450) to CRITICAL."""
        for p in range(0, 1001, 50):
            for count in (0, 1):
                c = classify_hsr_telemetry(p, hazard_proximity=False, persons_nearby_count=count)
                if p >= 450:
                    assert c == HSR_CRITICAL
                else:
                    assert c == HSR_CLEAR


# ----------------------------------------------------------------------------
# 7. Layer 1B: Worst-Severity Drain Invariants
# ----------------------------------------------------------------------------
class TestHSRDrainWorstSeverityInvariants:
    """Proves worst-severity-wins property across randomized observation batches."""

    def test_worst_severity_dominates_random_batches(self):
        rng = random.Random(FUZZ_SEED)
        states = [HSR_CLEAR, HSR_MONITOR, HSR_CRITICAL]

        for _ in range(1_000):
            batch_size = rng.randint(1, 10)
            batch = []
            has_crit = False
            has_mon = False

            for i in range(batch_size):
                st = rng.choice(states)
                if st == HSR_CRITICAL:
                    has_crit = True
                elif st == HSR_MONITOR:
                    has_mon = True

                p = HSRTelemetryPacket(
                    obs_id=i,
                    t_obs_us=1000 + i * 10,
                    t_emit_us=1000 + i * 10 + 5,
                    t_rx_us=2000,
                    distress_permille=500,
                    state=st,
                )
                batch.append(p)

            winning = drain_worst_severity(batch)
            assert winning is not None
            if has_crit:
                assert winning.state == HSR_CRITICAL
            elif has_mon:
                assert winning.state == HSR_MONITOR
            else:
                assert winning.state == HSR_CLEAR


# ----------------------------------------------------------------------------
# 8. Layer 1B: Stream Monitor & Dual-Gate Rebase Invariants
# ----------------------------------------------------------------------------
class TestHSRStreamMonitorInvariants:
    """Proves freeze latching and dual-gate dwell recovery invariants."""

    def test_freeze_latches_sticky_none(self):
        s = HSRStreamState()
        p1 = HSRTelemetryPacket(10, 1000, 1050, 1100, 0, HSR_CLEAR)
        s, status, _ = step_hsr_stream(s, [p1], now_us=1100)
        assert status == HSR_CLEAR

        # Frame freeze: identical obs_id=10
        p_frozen = HSRTelemetryPacket(10, 1032, 1050, 1100, 0, HSR_CLEAR)
        s, status, stamp = step_hsr_stream(s, [p_frozen], now_us=1132)
        assert s.frozen_latched is True
        assert status is None
        assert stamp is None

    def test_10k_stream_transitions_fuzzing(self):
        """Fuzzes 10,000 stream steps asserting fail-closed suppression invariants."""
        rng = random.Random(FUZZ_SEED)
        state = HSRStreamState()
        now_us = 1_000_000
        obs_id = 1

        for _ in range(10_000):
            now_us += 32_000
            # 85% normal advancing, 5% freeze, 5% regression, 5% empty tick
            r = rng.random()
            if r < 0.05:
                # Idle tick
                packets = []
            else:
                if r < 0.10:
                    pkt_obs = obs_id  # freeze
                elif r < 0.15:
                    pkt_obs = max(0, obs_id - rng.randint(1, 10))  # sequence regression
                else:
                    obs_id += 1
                    pkt_obs = obs_id

                st = rng.choice([HSR_CLEAR, HSR_CLEAR, HSR_CLEAR, HSR_MONITOR, HSR_CRITICAL])
                pkt = HSRTelemetryPacket(
                    obs_id=pkt_obs,
                    t_obs_us=now_us - rng.randint(5_000, 30_000),
                    t_emit_us=now_us - 1_000,
                    t_rx_us=now_us,
                    distress_permille=0 if st == HSR_CLEAR else (500 if st == HSR_MONITOR else 800),
                    state=st,
                )
                packets = [pkt]

            state, out_status, out_stamp = step_hsr_stream(state, packets, now_us=now_us)

            # --- HARD SAFETY INVARIANTS ---
            # Invariant 1: If latched in freeze or in rebase, output status MUST be None
            if state.frozen_latched or state.rebase_in_progress:
                assert out_status is None
                assert out_stamp is None

            # Invariant 2: Any emitted timestamp must never be in the future
            if out_status is not None:
                assert out_stamp is not None
                assert out_stamp <= now_us
