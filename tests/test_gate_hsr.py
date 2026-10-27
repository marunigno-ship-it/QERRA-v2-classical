# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Unit tests for QERRA Supervisory Gate -- QERRA-HSR reflex integration.
Verifies fail-closed clamping, fault latching, reset interlocks,
fail-closed behavior on missing/invalid HSR in required mode,
heartbeat freshness (stale-CLEAR detection), audit record logging,
and tamper-evident cryptographic replay through the flight recorder.
"""
import os
import tempfile
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
    initial_state,
    step,
)
from gate.gate_log import GateLogger
from verify_log import replay_log_file, verify_log_file


def _make_params(*, hsr_required: bool = False) -> GateParams:
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
        hsr_required=hsr_required,
        t_hsr_stale_us=96_000,
    )


class TestGateHsrIntegration(unittest.TestCase):
    def setUp(self):
        self.params = _make_params(hsr_required=False)
        self.params_required = _make_params(hsr_required=True)
        self.clean_ranges = [3.0, 3.0, 3.0, 3.0, 3.0]  # well clear of d_stop
        self.clean_proposal = Proposal(
            seq=1,
            sim_stamp_us=100_000,
            left_urad_s=2_000_000,
            right_urad_s=2_000_000,
            session_id=1,
        )

    def test_hsr_critical_trips_and_clamps_immediately(self):
        """Rule: HSR CRITICAL must force 0.0 rad/s within 1 tick and report TRIP_HSR_CRITICAL."""
        run_state = GateState(
            mode=Mode.RUN,
            last_tick_us=100_000,
            clear_since_us=None,
            held=self.clean_proposal,
            last_seq=1,
            last_cmd=(2_000_000, 2_000_000),
            last_session_id=1,
        )

        inp = GateInputs(
            sim_time_us=132_000,
            proposal=self.clean_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=132_000,
            raw_valid_points=5,
            hsr_status="CRITICAL",
            hsr_stamp_us=132_000,
        )

        res = step(run_state, self.params, inp)

        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)
        self.assertEqual(res.reason, Reason.TRIP_HSR_CRITICAL)

    def test_hsr_critical_latches_fail_closed(self):
        """Rule: A trip must latch. Even if HSR becomes CLEAR next tick, wheels stay at zero."""
        run_state = GateState(
            mode=Mode.RUN,
            last_tick_us=100_000,
            held=self.clean_proposal,
            last_seq=1,
            last_cmd=(2_000_000, 2_000_000),
            last_session_id=1,
        )
        inp1 = GateInputs(
            sim_time_us=132_000,
            proposal=self.clean_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=132_000,
            raw_valid_points=5,
            hsr_status="CRITICAL",
            hsr_stamp_us=132_000,
        )
        res1 = step(run_state, self.params, inp1)
        self.assertEqual(res1.state.mode, Mode.TRIPPED)

        inp2 = GateInputs(
            sim_time_us=164_000,
            proposal=self.clean_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=164_000,
            raw_valid_points=5,
            hsr_status="CLEAR",
            hsr_stamp_us=164_000,
        )
        res2 = step(res1.state, self.params, inp2)

        self.assertEqual(res2.state.mode, Mode.TRIPPED)
        self.assertEqual(res2.cmd_left_urad_s, 0)
        self.assertEqual(res2.cmd_right_urad_s, 0)
        self.assertEqual(res2.reason, Reason.LATCHED_DWELL)

    def test_operator_reset_rejected_while_hsr_critical(self):
        """Rule: If an operator sends a reset while HSR is CRITICAL, it must be rejected."""
        tripped_state = GateState(
            mode=Mode.TRIPPED,
            last_tick_us=100_000,
            clear_since_us=None,
            held=self.clean_proposal,
            last_seq=1,
            last_cmd=(0, 0),
            last_session_id=1,
        )

        inp = GateInputs(
            sim_time_us=132_000,
            proposal=self.clean_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=132_000,
            raw_valid_points=5,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status="CRITICAL",
            hsr_stamp_us=132_000,
        )

        res = step(tripped_state, self.params, inp)

        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)
        self.assertIn(Event.RESET_REJECTED_HAZARD, res.events)

    def test_operator_reset_rejected_in_awaiting_reset_while_hsr_monitor(self):
        """Rule: In AWAITING_RESET, a valid operator reset must be REJECTED if HSR is MONITOR."""
        awaiting_state = GateState(
            mode=Mode.AWAITING_RESET,
            last_tick_us=100_000,
            clear_since_us=100_000,
            held=self.clean_proposal,
            last_seq=1,
            last_cmd=(0, 0),
            last_session_id=1,
        )

        # Strictly fresh, valid proposal (seq=2) to isolate reset rejection without sequence warnings
        fresh_proposal = Proposal(
            seq=2,
            sim_stamp_us=132_000,
            left_urad_s=2_000_000,
            right_urad_s=2_000_000,
            session_id=1,
        )

        inp = GateInputs(
            sim_time_us=132_000,
            proposal=fresh_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=132_000,
            raw_valid_points=5,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status="MONITOR",
            hsr_stamp_us=132_000,
        )

        res = step(awaiting_state, self.params_required, inp)

        # The robot MUST NOT start driving!
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)
        self.assertEqual(res.events, (Event.RESET_REJECTED_HAZARD,))
        self.assertEqual(res.state.mode, Mode.AWAITING_RESET)

    def test_hsr_clear_allows_normal_cruise(self):
        """Rule: When HSR is CLEAR and fresh, normal proposals pass through unhindered."""
        run_state = GateState(
            mode=Mode.RUN,
            last_tick_us=100_000,
            held=self.clean_proposal,
            last_seq=1,
            last_cmd=(2_000_000, 2_000_000),
            last_session_id=1,
        )

        inp = GateInputs(
            sim_time_us=132_000,
            proposal=self.clean_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=132_000,
            raw_valid_points=5,
            hsr_status="CLEAR",
            hsr_stamp_us=132_000,
        )

        res = step(run_state, self.params, inp)

        self.assertEqual(res.state.mode, Mode.RUN)
        self.assertEqual(res.reason, Reason.PASS)
        self.assertEqual(res.cmd_left_urad_s, 2_000_000)
        self.assertEqual(res.cmd_right_urad_s, 2_000_000)

    def test_missing_hsr_trips_when_hsr_required(self):
        """Rule (ChatGPT Issue A): Silence must not mean safe. Missing HSR when required must trip TRIP_HSR_INVALID."""
        run_state = GateState(
            mode=Mode.RUN,
            last_tick_us=100_000,
            held=self.clean_proposal,
            last_seq=1,
            last_cmd=(2_000_000, 2_000_000),
            last_session_id=1,
        )

        inp = GateInputs(
            sim_time_us=132_000,
            proposal=self.clean_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=132_000,
            raw_valid_points=5,
            hsr_status=None,
        )

        res = step(run_state, self.params_required, inp)

        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)
        self.assertEqual(res.reason, Reason.TRIP_HSR_INVALID)

    def test_stale_hsr_clear_trips_fail_closed(self):
        """Rule (ChatGPT Issue 3): A frozen CLEAR status must trip TRIP_HSR_STALE once age > t_hsr_stale."""
        run_state = GateState(
            mode=Mode.RUN,
            last_tick_us=100_000,
            held=self.clean_proposal,
            last_seq=1,
            last_cmd=(2_000_000, 2_000_000),
            last_session_id=1,
        )

        # HSR sent "CLEAR", but its timestamp is 150 ms old (exceeds t_hsr_stale = 96 ms)
        inp = GateInputs(
            sim_time_us=250_000,
            proposal=self.clean_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=250_000,
            raw_valid_points=5,
            hsr_status="CLEAR",
            hsr_stamp_us=100_000,  # 150 ms old!
        )

        res = step(run_state, self.params_required, inp)

        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)
        self.assertEqual(res.reason, Reason.TRIP_HSR_STALE)

    def test_corrupted_hsr_trips_fail_closed(self):
        """Rule: An invalid/unrecognized HSR string must trip TRIP_HSR_INVALID."""
        run_state = GateState(
            mode=Mode.RUN,
            last_tick_us=100_000,
            held=self.clean_proposal,
            last_seq=1,
            last_cmd=(2_000_000, 2_000_000),
            last_session_id=1,
        )

        inp = GateInputs(
            sim_time_us=132_000,
            proposal=self.clean_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=132_000,
            raw_valid_points=5,
            hsr_status="UNKNOWN_CORRUPT_STATE",
            hsr_stamp_us=132_000,
        )

        res = step(run_state, self.params, inp)

        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)
        self.assertEqual(res.reason, Reason.TRIP_HSR_INVALID)

    def test_hsr_status_logged_in_audit_record(self):
        """Rule: Flight recorder must record hsr_status and hsr_age_us in root record and inputs dict."""
        inp = GateInputs(
            sim_time_us=100_000,
            proposal=self.clean_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=100_000,
            raw_valid_points=5,
            hsr_status="CRITICAL",
            hsr_stamp_us=100_000,
        )
        res = step(GateState(), self.params, inp)

        self.assertEqual(res.record["hsr_status"], "CRITICAL")
        self.assertEqual(res.record["inputs"]["hsr_status"], "CRITICAL")
        self.assertEqual(res.record["inputs"]["hsr_stamp_us"], 100_000)

    def test_deterministic_replay_verifies_hsr_trip_cycle(self):
        """
        End-to-End Black Box Test:
        Generates a multi-tick lifecycle log (boot -> dwell -> operator reset ->
        cruise -> HSR CRITICAL trip -> latched dwell), writes to a temporary
        gate_audit.jsonl, and proves that verify_log_file and replay_log_file
        reproduce every decision bit-for-bit without divergence.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "gate_audit.jsonl")
            logger = GateLogger(log_path, run_id="TEST_HSR_AUDIT_REPLAY", gate_version="0.3")
            state = initial_state()

            sim_time_us = 0
            seq_counter = 0

            # 1. Boot up and dwell for 33 ticks (~1.05s) to reach AWAITING_RESET
            for _ in range(33):
                seq_counter += 1
                sim_time_us += 32_000
                proposal = Proposal(
                    seq=seq_counter,
                    sim_stamp_us=sim_time_us,
                    left_urad_s=2_000_000,
                    right_urad_s=2_000_000,
                    session_id=1,
                )
                inp = GateInputs(
                    sim_time_us=sim_time_us,
                    proposal=proposal,
                    ranges_m=self.clean_ranges,
                    lidar_stamp_us=sim_time_us,
                    raw_valid_points=5,
                    hsr_status="CLEAR",
                    hsr_stamp_us=sim_time_us,
                )
                res = step(state, self.params, inp)
                state = res.state
                logger.append(res.record, wall_ns=sim_time_us * 1000)

            self.assertEqual(state.mode, Mode.AWAITING_RESET)

            # 2. Operator Reset Tick -> Transitions to RUN
            seq_counter += 1
            sim_time_us += 32_000
            proposal = Proposal(
                seq=seq_counter,
                sim_stamp_us=sim_time_us,
                left_urad_s=2_000_000,
                right_urad_s=2_000_000,
                session_id=1,
            )
            inp = GateInputs(
                sim_time_us=sim_time_us,
                proposal=proposal,
                ranges_m=self.clean_ranges,
                lidar_stamp_us=sim_time_us,
                raw_valid_points=5,
                reset_source=RESET_SOURCE_OPERATOR,
                hsr_status="CLEAR",
                hsr_stamp_us=sim_time_us,
            )
            res = step(state, self.params, inp)
            state = res.state
            logger.append(res.record, wall_ns=sim_time_us * 1000)
            self.assertEqual(state.mode, Mode.RUN)
            self.assertEqual(res.reason, Reason.RESET_ACCEPTED)

            # 3. Cruise for 5 ticks in RUN mode
            for _ in range(5):
                seq_counter += 1
                sim_time_us += 32_000
                proposal = Proposal(
                    seq=seq_counter,
                    sim_stamp_us=sim_time_us,
                    left_urad_s=2_000_000,
                    right_urad_s=2_000_000,
                    session_id=1,
                )
                inp = GateInputs(
                    sim_time_us=sim_time_us,
                    proposal=proposal,
                    ranges_m=self.clean_ranges,
                    lidar_stamp_us=sim_time_us,
                    raw_valid_points=5,
                    hsr_status="CLEAR",
                    hsr_stamp_us=sim_time_us,
                )
                res = step(state, self.params, inp)
                state = res.state
                logger.append(res.record, wall_ns=sim_time_us * 1000)
                self.assertEqual(state.mode, Mode.RUN)
                self.assertEqual(res.reason, Reason.PASS)

            # 4. Acute Distress Injected -> Trip on TRIP_HSR_CRITICAL
            seq_counter += 1
            sim_time_us += 32_000
            proposal = Proposal(
                seq=seq_counter,
                sim_stamp_us=sim_time_us,
                left_urad_s=2_000_000,
                right_urad_s=2_000_000,
                session_id=1,
            )
            inp = GateInputs(
                sim_time_us=sim_time_us,
                proposal=proposal,
                ranges_m=self.clean_ranges,
                lidar_stamp_us=sim_time_us,
                raw_valid_points=5,
                hsr_status="CRITICAL",
                hsr_stamp_us=sim_time_us,
            )
            res = step(state, self.params, inp)
            state = res.state
            logger.append(res.record, wall_ns=sim_time_us * 1000)
            self.assertEqual(state.mode, Mode.TRIPPED)
            self.assertEqual(res.reason, Reason.TRIP_HSR_CRITICAL)
            self.assertEqual(res.cmd_left_urad_s, 0)
            self.assertEqual(res.cmd_right_urad_s, 0)

            # 5. Next tick: HSR clears, but gate must remain latched
            seq_counter += 1
            sim_time_us += 32_000
            proposal = Proposal(
                seq=seq_counter,
                sim_stamp_us=sim_time_us,
                left_urad_s=2_000_000,
                right_urad_s=2_000_000,
                session_id=1,
            )
            inp = GateInputs(
                sim_time_us=sim_time_us,
                proposal=proposal,
                ranges_m=self.clean_ranges,
                lidar_stamp_us=sim_time_us,
                raw_valid_points=5,
                hsr_status="CLEAR",
                hsr_stamp_us=sim_time_us,
            )
            res = step(state, self.params, inp)
            state = res.state
            logger.append(res.record, wall_ns=sim_time_us * 1000)
            self.assertEqual(state.mode, Mode.TRIPPED)
            self.assertEqual(res.reason, Reason.LATCHED_DWELL)

            logger.close()

            # --- RUN AUDIT & REPLAY CHECKS ---
            audit_result = verify_log_file(log_path)
            self.assertTrue(audit_result.is_valid, f"Audit verification failed: {audit_result.error_message}")
            self.assertEqual(audit_result.total_records, 41)

            ok, count, err = replay_log_file(log_path, self.params)
            self.assertTrue(ok, f"Deterministic replay diverged: {err}")
            self.assertEqual(count, 41)


if __name__ == "__main__":
    unittest.main()
