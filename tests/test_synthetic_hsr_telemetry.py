# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Synthetic Asynchronous HSR Telemetry Stress Harness (Workstream 1).
Simulates an asynchronous perception node publishing telemetry to the Gate.
Verifies deterministic supervisory responses to:
- Steady telemetry streams
- Corrupted/NaN/Inf confidence values
- Dropped and delayed packets (heartbeat watchdog)
- Out-of-order packets
- Fault injection and dwell-gated recovery
"""
import math
from dataclasses import dataclass
from typing import Optional
import unittest

from gate.gate_core import (
    Event,
    GateInputs,
    GateParams,
    GateState,
    Mode,
    Proposal,
    Reason,
    RESET_SOURCE_OPERATOR,
    step,
)


@dataclass
class SyntheticHsrPacket:
    seq: int
    session_id: int
    stamp_us: int
    status: str
    confidence: float


class SyntheticHsrProducer:
    """Deterministic synthetic telemetry generator simulating an asynchronous sensor node."""

    def __init__(self, session_id: int = 1):
        self.session_id = session_id
        self.seq = 0

    def emit(self, stamp_us: int, confidence: float) -> SyntheticHsrPacket:
        self.seq += 1

        # Strict validation of floating-point confidence
        if (
            not isinstance(confidence, (int, float))
            or math.isnan(confidence)
            or math.isinf(confidence)
            or confidence < 0.0
            or confidence > 1.0
        ):
            status = "CORRUPTED_CONFIDENCE"
        elif confidence >= 0.80:
            status = "CRITICAL"
        elif confidence >= 0.50:
            status = "MONITOR"
        else:
            status = "CLEAR"

        return SyntheticHsrPacket(
            seq=self.seq,
            session_id=self.session_id,
            stamp_us=stamp_us,
            status=status,
            confidence=confidence,
        )


def _make_required_params() -> GateParams:
    return GateParams(
        lidar_n_expected=5,
        dt_us=32_000,
        t_watch_us=150_000,
        proposer_period_us=33_000,
        lidar_period_us=32_000,
        t_stale_us=96_000,
        t_dwell_us=1_000_000,
        max_tick_gap_us=64_000,
        wheel_radius_mm=98,
        w_min_urad_s=0,
        w_max_urad_s=3_000_000,
        a_design_mmps2=500,
        margin_mm=300,
        min_raw_lidar_returns=5,
        t_react_us=32_000,
        hsr_required=True,       # Fail-closed if HSR missing or stale
        t_hsr_stale_us=96_000,   # 3 ticks @ 32ms
    )


class TestSyntheticHsrTelemetry(unittest.TestCase):
    def setUp(self):
        self.params = _make_required_params()
        self.clean_ranges = [3.0, 3.0, 3.0, 3.0, 3.0]
        self.producer = SyntheticHsrProducer(session_id=1)
        self.initial_run_state = GateState(
            mode=Mode.RUN,
            last_tick_us=100_000,
            held=Proposal(seq=1, sim_stamp_us=100_000, left_urad_s=2_000_000, right_urad_s=2_000_000, session_id=1),
            last_seq=1,
            last_cmd=(2_000_000, 2_000_000),
            last_session_id=1,
        )

    def _make_proposal(self, seq: int, stamp_us: int) -> Proposal:
        return Proposal(seq=seq, sim_stamp_us=stamp_us, left_urad_s=2_000_000, right_urad_s=2_000_000, session_id=1)

    def test_synthetic_valid_steady_stream_maintains_run(self):
        """Invariant: Steady asynchronous CLEAR packets maintain uninterrupted RUN mode."""
        state = self.initial_run_state
        sim_time = 100_000

        for tick in range(10):
            sim_time += 32_000
            packet = self.producer.emit(stamp_us=sim_time, confidence=0.15)  # Steady CLEAR
            inp = GateInputs(
                sim_time_us=sim_time,
                proposal=self._make_proposal(tick + 2, sim_time),
                ranges_m=self.clean_ranges,
                lidar_stamp_us=sim_time,
                raw_valid_points=5,
                hsr_status=packet.status,
                hsr_stamp_us=packet.stamp_us,
            )
            res = step(state, self.params, inp)
            state = res.state

            self.assertEqual(state.mode, Mode.RUN)
            self.assertEqual(res.reason, Reason.PASS)
            self.assertEqual(res.cmd_left_urad_s, 2_000_000)
            self.assertEqual(res.cmd_right_urad_s, 2_000_000)

    def test_synthetic_nan_confidence_trips_invalid(self):
        """Invariant: NaN, Infinity, or out-of-range confidence must trip TRIP_HSR_INVALID fail-closed."""
        sim_time = 132_000
        packet = self.producer.emit(stamp_us=sim_time, confidence=float("nan"))

        inp = GateInputs(
            sim_time_us=sim_time,
            proposal=self._make_proposal(2, sim_time),
            ranges_m=self.clean_ranges,
            lidar_stamp_us=sim_time,
            raw_valid_points=5,
            hsr_status=packet.status,
            hsr_stamp_us=packet.stamp_us,
        )
        res = step(self.initial_run_state, self.params, inp)

        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)
        self.assertEqual(res.reason, Reason.TRIP_HSR_INVALID)

    def test_synthetic_packet_drop_triggers_watchdog(self):
        """Invariant: Dropped/stalled telemetry must trip TRIP_HSR_STALE once age exceeds 96 ms."""
        state = self.initial_run_state
        sim_time = 100_000

        # Producer emits one valid CLEAR packet at 132 ms, then crashes/goes silent
        sim_time += 32_000
        last_packet = self.producer.emit(stamp_us=sim_time, confidence=0.10)
        inp = GateInputs(
            sim_time_us=sim_time,
            proposal=self._make_proposal(2, sim_time),
            ranges_m=self.clean_ranges,
            lidar_stamp_us=sim_time,
            raw_valid_points=5,
            hsr_status=last_packet.status,
            hsr_stamp_us=last_packet.stamp_us,
        )
        res = step(state, self.params, inp)
        state = res.state
        self.assertEqual(state.mode, Mode.RUN)

        # 3 ticks pass with no new HSR telemetry (last timestamp frozen at 132 ms)
        for tick in range(3):
            sim_time += 32_000
            inp = GateInputs(
                sim_time_us=sim_time,
                proposal=self._make_proposal(tick + 3, sim_time),
                ranges_m=self.clean_ranges,
                lidar_stamp_us=sim_time,
                raw_valid_points=5,
                hsr_status=last_packet.status,       # Frozen status
                hsr_stamp_us=last_packet.stamp_us,   # Frozen timestamp (aging)
            )
            res = step(state, self.params, inp)
            state = res.state

        # At sim_time = 228 ms, age is (228 - 132) = 96 ms (<= 96 ms passes)
        # Next tick at sim_time = 260 ms, age is (260 - 132) = 128 ms (> 96 ms watchdog limit)
        sim_time += 32_000
        inp = GateInputs(
            sim_time_us=sim_time,
            proposal=self._make_proposal(6, sim_time),
            ranges_m=self.clean_ranges,
            lidar_stamp_us=sim_time,
            raw_valid_points=5,
            hsr_status=last_packet.status,
            hsr_stamp_us=last_packet.stamp_us,
        )
        res = step(state, self.params, inp)

        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)
        self.assertEqual(res.reason, Reason.TRIP_HSR_STALE)

    def test_synthetic_out_of_order_packet_does_not_revert_state(self):
        """Invariant: A delayed/out-of-order older packet arriving late cannot clear a tripped latch."""
        # 1. Acute distress arrives at t = 132 ms -> trips TRIPPED
        sim_time = 132_000
        critical_packet = self.producer.emit(stamp_us=sim_time, confidence=0.92)
        inp = GateInputs(
            sim_time_us=sim_time,
            proposal=self._make_proposal(2, sim_time),
            ranges_m=self.clean_ranges,
            lidar_stamp_us=sim_time,
            raw_valid_points=5,
            hsr_status=critical_packet.status,
            hsr_stamp_us=critical_packet.stamp_us,
        )
        res = step(self.initial_run_state, self.params, inp)
        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.reason, Reason.TRIP_HSR_CRITICAL)

        # 2. Next tick (t = 164 ms): network delays deliver an OLD packet stamped at t = 100 ms (CLEAR)
        sim_time = 164_000
        stale_delayed_packet = SyntheticHsrPacket(seq=0, session_id=1, stamp_us=100_000, status="CLEAR", confidence=0.10)
        inp_delayed = GateInputs(
            sim_time_us=sim_time,
            proposal=self._make_proposal(3, sim_time),
            ranges_m=self.clean_ranges,
            lidar_stamp_us=sim_time,
            raw_valid_points=5,
            hsr_status=stale_delayed_packet.status,
            hsr_stamp_us=stale_delayed_packet.stamp_us,
        )
        res_delayed = step(res.state, self.params, inp_delayed)

        # The latch MUST hold fail-closed!
        self.assertEqual(res_delayed.state.mode, Mode.TRIPPED)
        self.assertEqual(res_delayed.cmd_left_urad_s, 0)
        self.assertEqual(res_delayed.cmd_right_urad_s, 0)

    def test_synthetic_fault_recovery_requires_full_dwell_and_reset(self):
        """Invariant: When intermittent distress clears, recovery is blocked until 1.0 s dwell completes."""
        state = self.initial_run_state
        sim_time = 132_000

        # 1. Distress trips gate at t = 132 ms
        critical_packet = self.producer.emit(stamp_us=sim_time, confidence=0.88)
        inp = GateInputs(
            sim_time_us=sim_time,
            proposal=self._make_proposal(2, sim_time),
            ranges_m=self.clean_ranges,
            lidar_stamp_us=sim_time,
            raw_valid_points=5,
            hsr_status=critical_packet.status,
            hsr_stamp_us=critical_packet.stamp_us,
        )
        res = step(state, self.params, inp)
        state = res.state
        self.assertEqual(state.mode, Mode.TRIPPED)

        # 2. Distress clears. Dwell begins. Run 10 ticks (320 ms).
        for tick in range(10):
            sim_time += 32_000
            clear_packet = self.producer.emit(stamp_us=sim_time, confidence=0.10)
            inp = GateInputs(
                sim_time_us=sim_time,
                proposal=self._make_proposal(tick + 3, sim_time),
                ranges_m=self.clean_ranges,
                lidar_stamp_us=sim_time,
                raw_valid_points=5,
                hsr_status=clear_packet.status,
                hsr_stamp_us=clear_packet.stamp_us,
            )
            res = step(state, self.params, inp)
            state = res.state
            self.assertEqual(state.mode, Mode.TRIPPED)
            self.assertEqual(res.reason, Reason.LATCHED_DWELL)

        # 3. Premature operator reset at tick 11 (only ~352 ms into 1.0 s dwell) MUST be REJECTED
        sim_time += 32_000
        clear_packet = self.producer.emit(stamp_us=sim_time, confidence=0.10)
        reset_inp = GateInputs(
            sim_time_us=sim_time,
            proposal=self._make_proposal(13, sim_time),
            ranges_m=self.clean_ranges,
            lidar_stamp_us=sim_time,
            raw_valid_points=5,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status=clear_packet.status,
            hsr_stamp_us=clear_packet.stamp_us,
        )
        res_premature = step(state, self.params, reset_inp)
        self.assertIn(Event.RESET_REJECTED_NOT_READY, res_premature.events)
        self.assertEqual(res_premature.state.mode, Mode.TRIPPED)
        state = res_premature.state

        # 4. Continue clear dwell for 22 more ticks (total continuous clear: (10 + 1 + 22) * 32 ms = 1056 ms >= 1.0 s)
        for tick in range(22):
            sim_time += 32_000
            clear_packet = self.producer.emit(stamp_us=sim_time, confidence=0.10)
            inp = GateInputs(
                sim_time_us=sim_time,
                proposal=self._make_proposal(tick + 14, sim_time),
                ranges_m=self.clean_ranges,
                lidar_stamp_us=sim_time,
                raw_valid_points=5,
                hsr_status=clear_packet.status,
                hsr_stamp_us=clear_packet.stamp_us,
            )
            res = step(state, self.params, inp)
            state = res.state

        # The gate must now have completed dwell and be in AWAITING_RESET
        self.assertEqual(state.mode, Mode.AWAITING_RESET)
        self.assertEqual(res.reason, Reason.LATCHED_AWAIT_RESET)

        # 5. Authorized operator reset is sent -> State transitions to RUN (cmd holds 0 on reset tick)
        sim_time += 32_000
        clear_packet = self.producer.emit(stamp_us=sim_time, confidence=0.10)
        valid_reset_inp = GateInputs(
            sim_time_us=sim_time,
            proposal=self._make_proposal(36, sim_time),
            ranges_m=self.clean_ranges,
            lidar_stamp_us=sim_time,
            raw_valid_points=5,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status=clear_packet.status,
            hsr_stamp_us=clear_packet.stamp_us,
        )
        res_reset = step(state, self.params, valid_reset_inp)
        self.assertEqual(res_reset.state.mode, Mode.RUN)
        self.assertEqual(res_reset.reason, Reason.RESET_ACCEPTED)
        self.assertEqual(res_reset.cmd_left_urad_s, 0)
        self.assertEqual(res_reset.cmd_right_urad_s, 0)

        # 6. Subsequent running tick -> Full cruise speed resumes (Reason.PASS)
        sim_time += 32_000
        clear_packet = self.producer.emit(stamp_us=sim_time, confidence=0.10)
        run_inp = GateInputs(
            sim_time_us=sim_time,
            proposal=self._make_proposal(37, sim_time),
            ranges_m=self.clean_ranges,
            lidar_stamp_us=sim_time,
            raw_valid_points=5,
            hsr_status=clear_packet.status,
            hsr_stamp_us=clear_packet.stamp_us,
        )
        res_recovered = step(res_reset.state, self.params, run_inp)
        self.assertEqual(res_recovered.state.mode, Mode.RUN)
        self.assertEqual(res_recovered.reason, Reason.PASS)
        self.assertEqual(res_recovered.cmd_left_urad_s, 2_000_000)
        self.assertEqual(res_recovered.cmd_right_urad_s, 2_000_000)


if __name__ == "__main__":
    unittest.main()
