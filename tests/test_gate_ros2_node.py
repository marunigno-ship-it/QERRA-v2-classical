# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""Unit tests for QERRA ROS 2 gate node translators and HSR reflex receiver (stdlib only)."""
from __future__ import annotations

import json
import math
import os
import socket
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

# Ensure repository root is on sys.path when test is run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gate.gate_config import get_live_gate_params
from gate.gate_core import (
    GateInputs,
    GateState,
    Mode,
    Reason,
    RESET_SOURCE_OPERATOR,
    initial_state,
    step,
)
from gate.gate_log import GateLogger, capture_harness_manifest
from ros2.hsr_receiver import HsrReceiver
from ros2.qerra_gate_node import (
    DEFAULT_TRACK_WIDTH_M,
    DEFAULT_WHEEL_RADIUS_M,
    DEFAULT_ROBOT_HALF_WIDTH_M,
    DEFAULT_T_REACT_MS,
    DEFAULT_LIDAR_PERIOD_MS,
    DEFAULT_LIDAR_STALE_MS,
    DEFAULT_HSR_TOPIC,
    NODE_VERSION,
    ROS2_AVAILABLE,
    create_lidar_pipeline,
    format_gate_state_json,
    process_laser_scan,
    require_ros2,
    twist_to_proposal,
    twist_to_wheel_speeds,
    wheel_speeds_to_twist,
)
from verify_log import replay_log_file, verify_log_file


class TestGateRos2Translators(unittest.TestCase):
    """Verifies kinematic and lidar translators for the QERRA ROS 2 gate node."""

    def test_version_and_import_guard(self) -> None:
        """Confirms node metadata and that require_ros2 fails loudly on Windows."""
        self.assertEqual(NODE_VERSION, "0.3.2")
        self.assertEqual(DEFAULT_HSR_TOPIC, "/hsr/telemetry")
        if not ROS2_AVAILABLE:
            with self.assertRaises(RuntimeError):
                require_ros2()

    def test_straight_line_nominal(self) -> None:
        """Cruise speed 0.20 m/s translates equally to both wheels with roundtrip parity."""
        left, right = twist_to_wheel_speeds(0.20, 0.0)
        self.assertEqual(left, right)
        self.assertEqual(left, 2_040_816)

        linear_x, angular_z = wheel_speeds_to_twist(left, right)
        self.assertAlmostEqual(linear_x, 0.20, places=4)
        self.assertAlmostEqual(angular_z, 0.0, places=4)

    def test_pure_yaw_rotation(self) -> None:
        """Pure in-place spin produces equal and opposite wheel velocities."""
        left, right = twist_to_wheel_speeds(0.0, 1.0)
        self.assertEqual(left, -right)

        linear_x, angular_z = wheel_speeds_to_twist(left, right)
        self.assertAlmostEqual(linear_x, 0.0, places=4)
        self.assertAlmostEqual(angular_z, 1.0, places=4)

    def test_proposal_structure(self) -> None:
        """Constructs an immutable gate Proposal with microsecond stamps."""
        p = twist_to_proposal(seq=42, sim_stamp_us=1_000_000, linear_x_mps=0.20, angular_z_radps=0.0)
        self.assertEqual(p.seq, 42)
        self.assertEqual(p.sim_stamp_us, 1_000_000)
        self.assertEqual(p.left_urad_s, 2_040_816)
        self.assertEqual(p.right_urad_s, 2_040_816)
        self.assertEqual(p.session_id, 0)

    def test_non_finite_rejection_fail_closed(self) -> None:
        """Rejects NaN and Inf fail-closed."""
        with self.assertRaises(ValueError):
            twist_to_wheel_speeds(float("nan"), 0.0)
        with self.assertRaises(ValueError):
            twist_to_wheel_speeds(0.20, float("inf"))

    def test_non_finite_twist_rejection_all_variants(self) -> None:
        """Verifies that NaN, +Inf, and -Inf in linear or angular velocities fail closed with ValueError."""
        non_finites = [float("nan"), float("inf"), float("-inf")]
        for val in non_finites:
            with self.subTest(linear_val=val):
                with self.assertRaises(ValueError):
                    twist_to_proposal(seq=1, sim_stamp_us=100_000, linear_x_mps=val, angular_z_radps=0.0)
            with self.subTest(angular_val=val):
                with self.assertRaises(ValueError):
                    twist_to_proposal(seq=1, sim_stamp_us=100_000, linear_x_mps=0.20, angular_z_radps=val)

    def test_proposal_invalid_inhibition_and_telemetry(self) -> None:
        """
        Phase 1: Verifies that proposal_invalid=True forces wheel speeds to zero,
        translates to (0.0, 0.0) Twist, and emits Event.MSG_REJECTED_INVALID in /gate/state JSON.
        """
        params = get_live_gate_params(lidar_n_expected=5, hsr_required=False)
        state = GateState(mode=Mode.RUN, last_tick_us=100_000 - 32_000)

        prop = twist_to_proposal(1, 100_000, 0.20, 0.0)
        res_cruise = step(state, params, GateInputs(
            sim_time_us=100_000,
            proposal=prop,
            ranges_m=[2.0] * 5,
            lidar_stamp_us=100_000,
        ))
        self.assertEqual(res_cruise.state.mode, Mode.RUN)

        res_inhibited = step(res_cruise.state, params, GateInputs(
            sim_time_us=132_000,
            proposal=None,
            proposal_invalid=True,
            ranges_m=[2.0] * 5,
            lidar_stamp_us=132_000,
        ))
        self.assertEqual(res_inhibited.cmd_left_urad_s, 0)
        self.assertEqual(res_inhibited.cmd_right_urad_s, 0)
        self.assertEqual(res_inhibited.state.mode, Mode.RUN)

        lin_x, ang_z = wheel_speeds_to_twist(
            res_inhibited.cmd_left_urad_s, res_inhibited.cmd_right_urad_s
        )
        self.assertEqual(lin_x, 0.0)
        self.assertEqual(ang_z, 0.0)

        telemetry = json.loads(format_gate_state_json(res_inhibited.state, res_inhibited.record))
        self.assertEqual(telemetry["mode"], "RUN")
        self.assertIn("MSG_REJECTED_INVALID", telemetry["events"])
        self.assertEqual(telemetry["cmd_left_urad_s"], 0)
        self.assertEqual(telemetry["cmd_right_urad_s"], 0)

    def test_standstill_and_odometry_telemetry(self) -> None:
        """
        Verifies that format_gate_state_json correctly serializes meas_left_urad_s,
        meas_right_urad_s, and standstill_ok under fresh, moving, standstill, and stale states.
        """
        params_std = get_live_gate_params(lidar_n_expected=5, hsr_required=False, standstill_required=True)
        state = initial_state()

        inp_moving = GateInputs(
            sim_time_us=100_000,
            proposal=twist_to_proposal(1, 100_000, 0.20, 0.0),
            ranges_m=[2.0] * 5,
            lidar_stamp_us=100_000,
            meas_left_urad_s=2_040_816,
            meas_right_urad_s=2_040_816,
        )
        res_moving = step(state, params_std, inp_moving)
        json_moving = json.loads(format_gate_state_json(
            res_moving.state,
            res_moving.record,
            standstill_required=True,
            standstill_ok=False,
        ))
        self.assertEqual(json_moving["meas_left_urad_s"], 2_040_816)
        self.assertEqual(json_moving["meas_right_urad_s"], 2_040_816)
        self.assertTrue(json_moving["standstill_required"])
        self.assertFalse(json_moving["standstill_ok"])

        inp_still = GateInputs(
            sim_time_us=132_000,
            proposal=twist_to_proposal(2, 132_000, 0.0, 0.0),
            ranges_m=[2.0] * 5,
            lidar_stamp_us=132_000,
            meas_left_urad_s=0,
            meas_right_urad_s=0,
        )
        res_still = step(res_moving.state, params_std, inp_still)
        json_still = json.loads(format_gate_state_json(
            res_still.state,
            res_still.record,
            standstill_required=True,
            standstill_ok=True,
        ))
        self.assertEqual(json_still["meas_left_urad_s"], 0)
        self.assertEqual(json_still["meas_right_urad_s"], 0)
        self.assertTrue(json_still["standstill_ok"])

        inp_stale = GateInputs(
            sim_time_us=164_000,
            proposal=twist_to_proposal(3, 164_000, 0.20, 0.0),
            ranges_m=[2.0] * 5,
            lidar_stamp_us=164_000,
            meas_left_urad_s=None,
            meas_right_urad_s=None,
        )
        res_stale = step(res_still.state, params_std, inp_stale)
        json_stale = json.loads(format_gate_state_json(
            res_stale.state,
            res_stale.record,
            standstill_required=True,
            standstill_ok=False,
        ))
        self.assertIsNone(json_stale["meas_left_urad_s"])
        self.assertIsNone(json_stale["meas_right_urad_s"])
        self.assertFalse(json_stale["standstill_ok"])

        json_openloop = json.loads(format_gate_state_json(
            res_stale.state,
            res_stale.record,
            standstill_required=False,
            standstill_ok=True,
        ))
        self.assertFalse(json_openloop["standstill_required"])
        self.assertTrue(json_openloop["standstill_ok"])

    def test_lidar_corridor_filter_and_timestamp(self) -> None:
        """Preserves corridor returns, masks outer returns to +inf, and converts timestamps."""
        pipeline = create_lidar_pipeline(n_samples=5, fov_rad=math.pi, half_width_m=0.32)

        raw_ranges = [2.0, 1.0, 0.5, 1.0, 2.0]
        filtered, stamp_us, valid_pts = process_laser_scan(
            raw_ranges, stamp_sec=2, stamp_nanosec=250_000_000, pipeline=pipeline
        )

        self.assertEqual(stamp_us, 2_250_000)
        self.assertEqual(valid_pts, 5)
        self.assertEqual(len(filtered), 5)
        self.assertEqual(filtered[2], 0.5)
        self.assertTrue(math.isinf(filtered[0]))
        self.assertTrue(math.isinf(filtered[4]))

    def test_lidar_stalled_hardware_watchdog(self) -> None:
        """When sensor acquisition stalls, the acquisition timestamp does not advance."""
        pipeline = create_lidar_pipeline(n_samples=3, fov_rad=1.0)

        _, stamp_1, _ = process_laser_scan([1.0, 1.0, 1.0], 1, 0, pipeline, stalled=False)
        self.assertEqual(stamp_1, 1_000_000)

        _, stamp_2, _ = process_laser_scan([1.0, 1.0, 1.0], 2, 0, pipeline, stalled=True)
        self.assertEqual(stamp_2, 1_000_000)

    def test_lidar_negative_timestamp_rejected(self) -> None:
        """Rejects negative timestamp fields fail-closed."""
        pipeline = create_lidar_pipeline(n_samples=3, fov_rad=1.0)
        with self.assertRaises(ValueError):
            process_laser_scan([1.0, 1.0, 1.0], -1, 0, pipeline)
        with self.assertRaises(ValueError):
            process_laser_scan([1.0, 1.0, 1.0], 0, -500, pipeline)

    def test_reaction_time_envelope_growth_and_telemetry(self) -> None:
        """Verifies that t_react parameterization grows stopping envelope and serializes to telemetry."""
        p_32 = get_live_gate_params(lidar_n_expected=5, t_react_us=32_000)
        p_96 = get_live_gate_params(lidar_n_expected=5, t_react_us=96_000)
        p_160 = get_live_gate_params(lidar_n_expected=5, t_react_us=160_000)

        prop = twist_to_proposal(1, 100_000, 0.20, 0.0)
        inp = GateInputs(sim_time_us=100_000, proposal=prop, ranges_m=[2.0] * 5, lidar_stamp_us=100_000)

        res_32 = step(initial_state(), p_32, inp)
        res_96 = step(initial_state(), p_96, inp)
        res_160 = step(initial_state(), p_160, inp)

        self.assertEqual(res_32.record["d_stop_mm"], 347)
        self.assertEqual(res_96.record["d_stop_mm"], 360)
        self.assertEqual(res_160.record["d_stop_mm"], 372)

        json_str = format_gate_state_json(res_96.state, res_96.record, t_react_us=96_000)
        data = json.loads(json_str)
        self.assertEqual(data["t_react_us"], 96_000)
        self.assertEqual(DEFAULT_T_REACT_MS, 96.0)

    def test_hardware_profile_timing_parameters_and_invariant_guard(self) -> None:
        """Verifies separation of 10 Hz hardware vs 32 ms simulation timing profiles."""
        hw_params = get_live_gate_params(
            lidar_n_expected=682,
            dt_us=32_000,
            lidar_period_us=100_000,
            t_stale_us=300_000,
            t_react_us=160_000,
        )
        self.assertEqual(hw_params.lidar_period_us, 100_000)
        self.assertEqual(hw_params.t_stale_us, 300_000)
        self.assertEqual(hw_params.t_react_us, 160_000)
        self.assertGreaterEqual(hw_params.t_stale_us, 2 * hw_params.lidar_period_us + hw_params.dt_us)

        with self.assertRaises(ValueError):
            get_live_gate_params(
                lidar_n_expected=682,
                dt_us=32_000,
                lidar_period_us=100_000,
                t_stale_us=96_000,
            )

        res = step(initial_state(), hw_params, GateInputs(sim_time_us=100_000))
        json_str = format_gate_state_json(
            res.state,
            res.record,
            t_react_us=160_000,
            lidar_stale_us=300_000,
            lidar_period_us=100_000,
        )
        data = json.loads(json_str)
        self.assertEqual(data["lidar_period_us"], 100_000)
        self.assertEqual(data["lidar_stale_us"], 300_000)
        self.assertEqual(data["t_react_us"], 160_000)
        self.assertEqual(DEFAULT_LIDAR_PERIOD_MS, 32.0)
        self.assertEqual(DEFAULT_LIDAR_STALE_MS, 96.0)

    def test_10hz_dt_us_scales_max_tick_gap_and_allows_dwell_recovery(self) -> None:
        """Regression test for 10 Hz dwell scaling."""
        dt_10hz = 100_000
        params = get_live_gate_params(
            lidar_n_expected=5,
            dt_us=dt_10hz,
            lidar_period_us=100_000,
            t_stale_us=300_000,
            t_react_us=160_000,
            hsr_required=False,
        )
        self.assertEqual(params.dt_us, 100_000)
        self.assertEqual(params.max_tick_gap_us, 200_000)

        state = initial_state()
        ranges = [2.0] * 5
        sim_t = 100_000

        for seq in range(1, 12):
            prop = twist_to_proposal(seq, sim_t, 0.20, 0.0)
            res = step(state, params, GateInputs(
                sim_time_us=sim_t,
                proposal=prop,
                ranges_m=ranges,
                lidar_stamp_us=sim_t,
            ))
            state = res.state
            sim_t += dt_10hz

        self.assertEqual(state.mode, Mode.AWAITING_RESET)

        res_reset = step(state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=twist_to_proposal(12, sim_t, 0.20, 0.0),
            ranges_m=ranges,
            lidar_stamp_us=sim_t,
            reset_source=RESET_SOURCE_OPERATOR,
        ))
        self.assertEqual(res_reset.reason, Reason.RESET_ACCEPTED)
        self.assertEqual(res_reset.state.mode, Mode.RUN)

        sim_t += dt_10hz
        res_run = step(res_reset.state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=twist_to_proposal(13, sim_t, 0.20, 0.0),
            ranges_m=ranges,
            lidar_stamp_us=sim_t,
        ))
        self.assertEqual(res_run.state.mode, Mode.RUN)
        self.assertEqual(res_run.reason, Reason.PASS)
        self.assertGreater(res_run.cmd_left_urad_s, 0)

    def test_flight_logger_cryptographic_verification_and_replay(self) -> None:
        """Verifies that GateLogger produces a valid SHA-256 hash chain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "flight_test.jsonl")
            params = get_live_gate_params(lidar_n_expected=5, hsr_required=False)
            manifest = capture_harness_manifest()
            manifest["params"] = asdict(params)

            logger = GateLogger(
                filepath=log_path,
                run_id="test_run_p7",
                gate_version="0.4",
                manifest=manifest,
            )

            state = initial_state()
            dt_us = 32_000
            sim_t = 100_000
            ranges = [2.0] * 5

            for seq in range(1, 6):
                sim_t += dt_us
                prop = twist_to_proposal(seq, sim_t, 0.20, 0.0)
                res = step(state, params, GateInputs(
                    sim_time_us=sim_t,
                    proposal=prop,
                    ranges_m=ranges,
                    lidar_stamp_us=sim_t,
                ))
                state = res.state
                logger.append(res.record, wall_ns=sim_t * 1_000)

            logger.close()

            audit_res = verify_log_file(log_path)
            self.assertTrue(audit_res.is_valid, f"Audit failed: {audit_res.error_message}")
            self.assertEqual(audit_res.total_records, 5)
            self.assertEqual(audit_res.first_seq, 0)
            self.assertEqual(audit_res.last_seq, 4)
            self.assertIsNotNone(audit_res.head_hash)

            replay_ok, count, err = replay_log_file(log_path, params)
            self.assertTrue(replay_ok, f"Replay failed: {err}")
            self.assertEqual(count, 5)

    def test_flight_logger_failure_trips_r10_fail_closed(self) -> None:
        """Verifies that log_write_failed=True immediately trips Reason.TRIP_LOG_FAILURE (R-10)."""
        params = get_live_gate_params(lidar_n_expected=5, hsr_required=False)
        prop = twist_to_proposal(1, 100_000, 0.20, 0.0)

        res = step(initial_state(), params, GateInputs(
            sim_time_us=100_000,
            proposal=prop,
            ranges_m=[2.0] * 5,
            lidar_stamp_us=100_000,
            log_write_failed=True,
        ))
        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.reason, Reason.TRIP_LOG_FAILURE)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)


class TestHsrReceiverAndReflexIntegration(unittest.TestCase):
    """Verifies HSR UDP reflex receiver, topic-push pathway, and Layer 1B trip enforcement."""

    def test_hsr_receiver_disabled_returns_none(self) -> None:
        """When HSR source is disabled, poll always returns (None, None)."""
        rx = HsrReceiver(enabled=False)
        self.addCleanup(rx.close)
        status, stamp = rx.poll(now_us=100_000)
        self.assertIsNone(status)
        self.assertIsNone(stamp)

    def test_hsr_receiver_topic_push_pathway_drives_gate_core(self) -> None:
        """
        Verifies that HsrReceiver with use_socket=False consumes in-memory pushed JSON
        payloads (the ROS 2 native /hsr/telemetry topic pathway), instantiates zero sockets,
        enforces dwell recovery, and trips Gate Core on acute distress.
        """
        rx = HsrReceiver(enabled=True, use_socket=False)
        self.addCleanup(rx.close)

        self.assertFalse(rx.use_socket)
        self.assertIsNone(rx._sock, "Topic-push receiver must never instantiate a UDP socket")

        params = get_live_gate_params(lidar_n_expected=5, hsr_required=True)
        ranges = [2.0] * 5
        dt_us = 32_000
        sim_t = 100_000

        # Push initial valid CLEAR payload conforming to v0.4.0 3-vector contract
        payload_clear = json.dumps({
            "obs_id": 1,
            "t_obs_us": sim_t,
            "t_emit_us": sim_t + 1_000,
            "distress_permille": 0,
            "state": "CLEAR",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        })
        rx.push(payload_clear)

        status, stamp = rx.poll(now_us=sim_t + 2_000)
        self.assertEqual(status, "CLEAR")
        self.assertEqual(stamp, sim_t)
        self.assertEqual(rx.packets_drained_total, 1)

        # 1. Drive gate core through dwell
        state = initial_state()
        for seq in range(1, 36):
            sim_t += dt_us
            pkt = json.dumps({
                "obs_id": 1 + seq,
                "t_obs_us": sim_t,
                "t_emit_us": sim_t + 1_000,
                "distress_permille": 0,
                "state": "CLEAR",
                "hazard_proximity": False,
                "persons_nearby_count": 2,
            })
            rx.push(pkt)
            st, t_st = rx.poll(now_us=sim_t + 2_000)
            res = step(state, params, GateInputs(
                sim_time_us=sim_t,
                proposal=twist_to_proposal(seq, sim_t, 0.20, 0.0),
                ranges_m=ranges,
                lidar_stamp_us=sim_t,
                hsr_status=st,
                hsr_stamp_us=t_st,
            ))
            state = res.state

        self.assertEqual(state.mode, Mode.AWAITING_RESET)

        # 2. Operator reset accepted -> RUN
        sim_t += dt_us
        rx.push(json.dumps({
            "obs_id": 38,
            "t_obs_us": sim_t,
            "t_emit_us": sim_t + 1_000,
            "distress_permille": 0,
            "state": "CLEAR",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        }))
        st, t_st = rx.poll(now_us=sim_t + 2_000)
        res_reset = step(state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=twist_to_proposal(38, sim_t, 0.20, 0.0),
            ranges_m=ranges,
            lidar_stamp_us=sim_t,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status=st,
            hsr_stamp_us=t_st,
        ))
        state = res_reset.state
        self.assertEqual(state.mode, Mode.RUN)

        # 3. Push acute distress payload -> Gate trips TRIP_HSR_CRITICAL
        sim_t += dt_us
        payload_distress = json.dumps({
            "obs_id": 39,
            "t_obs_us": sim_t,
            "t_emit_us": sim_t + 1_000,
            "distress_permille": 850,
            "state": "CRITICAL",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        })
        rx.push(payload_distress)
        crit_st, crit_t_st = rx.poll(now_us=sim_t + 2_000)
        self.assertEqual(crit_st, "CRITICAL")

        res_crit = step(state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=twist_to_proposal(39, sim_t, 0.20, 0.0),
            ranges_m=ranges,
            lidar_stamp_us=sim_t,
            hsr_status=crit_st,
            hsr_stamp_us=crit_t_st,
        ))
        self.assertEqual(res_crit.state.mode, Mode.TRIPPED)
        self.assertEqual(res_crit.reason, Reason.TRIP_HSR_CRITICAL)
        self.assertEqual(res_crit.cmd_left_urad_s, 0)
        self.assertEqual(res_crit.cmd_right_urad_s, 0)

    def test_hsr_receiver_udp_distress_trips_gate_core(self) -> None:
        """Recovery from a latched trip, then acute distress (CRITICAL) via UDP trips the gate."""
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(test_sock.close)
        test_sock.setblocking(False)
        test_sock.bind(("127.0.0.1", 0))
        port = test_sock.getsockname()[1]

        rx = HsrReceiver(port=port, enabled=True, sock=test_sock)
        self.addCleanup(rx.close)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sender.close)

        params = get_live_gate_params(lidar_n_expected=5, hsr_required=False)
        ranges = [2.0, 2.0, 2.0, 2.0, 2.0]
        dt_us = 32_000

        clear_payload = json.dumps({
            "obs_id": 1,
            "t_obs_us": 100_000,
            "t_emit_us": 101_000,
            "distress_permille": 0,
            "state": "CLEAR",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        }).encode("utf-8")
        sender.sendto(clear_payload, ("127.0.0.1", port))

        sim_t = 100_000
        status, stamp = rx.poll(now_us=sim_t)
        self.assertEqual(status, "CLEAR")
        self.assertEqual(stamp, 100_000)

        state = initial_state()
        for seq in range(1, 36):
            sim_t += dt_us
            prop = twist_to_proposal(seq, sim_t, 0.20, 0.0)
            res = step(state, params, GateInputs(
                sim_time_us=sim_t,
                proposal=prop,
                ranges_m=ranges,
                lidar_stamp_us=sim_t,
                hsr_status=status,
                hsr_stamp_us=stamp,
            ))
            state = res.state

        self.assertEqual(state.mode, Mode.AWAITING_RESET)

        sim_t += dt_us
        prop_reset = twist_to_proposal(36, sim_t, 0.20, 0.0)
        res = step(state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=prop_reset,
            ranges_m=ranges,
            lidar_stamp_us=sim_t,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status="CLEAR",
            hsr_stamp_us=sim_t,
        ))
        state = res.state
        self.assertEqual(state.mode, Mode.RUN)
        self.assertEqual(res.reason, Reason.RESET_ACCEPTED)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)

        sim_t += dt_us
        prop_run = twist_to_proposal(37, sim_t, 0.20, 0.0)
        res_run = step(state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=prop_run,
            ranges_m=ranges,
            lidar_stamp_us=sim_t,
            hsr_status="CLEAR",
            hsr_stamp_us=sim_t,
        ))
        state = res_run.state
        self.assertEqual(state.mode, Mode.RUN)
        self.assertEqual(res_run.reason, Reason.PASS)
        self.assertGreater(res_run.cmd_left_urad_s, 0)
        self.assertGreater(res_run.cmd_right_urad_s, 0)

        distress_payload = json.dumps({
            "obs_id": 2,
            "t_obs_us": sim_t + dt_us,
            "t_emit_us": sim_t + dt_us + 1_000,
            "distress_permille": 850,
            "state": "CRITICAL",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        }).encode("utf-8")
        sender.sendto(distress_payload, ("127.0.0.1", port))

        sim_t += dt_us
        crit_status, crit_stamp = rx.poll(now_us=sim_t)
        self.assertEqual(crit_status, "CRITICAL")
        self.assertEqual(crit_stamp, sim_t)

        prop_crit = twist_to_proposal(38, sim_t, 0.20, 0.0)
        crit_res = step(state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=prop_crit,
            ranges_m=ranges,
            lidar_stamp_us=sim_t,
            hsr_status=crit_status,
            hsr_stamp_us=crit_stamp,
        ))

        self.assertEqual(crit_res.state.mode, Mode.TRIPPED)
        self.assertEqual(crit_res.reason, Reason.TRIP_HSR_CRITICAL)
        self.assertEqual(crit_res.cmd_left_urad_s, 0)
        self.assertEqual(crit_res.cmd_right_urad_s, 0)

    def test_hsr_receiver_post_reset_continuity_across_40ms_and_50ms_phases(self) -> None:
        """Regression test for 25 Hz and 20 Hz timing phase continuity."""
        dt_us = 32_000
        ranges = [2.0] * 5
        params = get_live_gate_params(lidar_n_expected=5, hsr_required=True)

        for period_ms in (40, 50):
            period_us = period_ms * 1_000
            for phase_ms in range(period_ms):
                phase_us = phase_ms * 1_000
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                rx = None
                try:
                    test_sock.setblocking(False)
                    test_sock.bind(("127.0.0.1", 0))
                    port = test_sock.getsockname()[1]
                    rx = HsrReceiver(port=port, enabled=True, sock=test_sock)

                    sim_t = 1_000_000
                    next_emit_us = sim_t + phase_us
                    obs_id = 0
                    seq = 0
                    state = initial_state()

                    def _step_tick(reset_src=None):
                        nonlocal sim_t, next_emit_us, obs_id, seq, state
                        while next_emit_us <= sim_t:
                            obs_id += 1
                            pkt = json.dumps({
                                "obs_id": obs_id,
                                "t_obs_us": next_emit_us,
                                "t_emit_us": next_emit_us + 1_000,
                                "distress_permille": 0,
                                "state": "CLEAR",
                                "hazard_proximity": False,
                                "persons_nearby_count": 2,
                            }).encode("utf-8")
                            sender.sendto(pkt, ("127.0.0.1", port))
                            next_emit_us += period_us

                        status, stamp = rx.poll(now_us=sim_t)
                        seq += 1
                        prop = twist_to_proposal(seq, sim_t, 0.20, 0.0)
                        res = step(state, params, GateInputs(
                            sim_time_us=sim_t,
                            proposal=prop,
                            ranges_m=ranges,
                            lidar_stamp_us=sim_t,
                            reset_source=reset_src,
                            hsr_status=status,
                            hsr_stamp_us=stamp,
                        ))
                        state = res.state
                        sim_t += dt_us
                        return res

                    for _ in range(50):
                        _step_tick()
                        if state.mode == Mode.AWAITING_RESET:
                            break
                    self.assertEqual(
                        state.mode,
                        Mode.AWAITING_RESET,
                        f"Failed to reach AWAITING_RESET at period={period_ms}ms phase={phase_ms}ms",
                    )

                    res_reset = _step_tick(reset_src=RESET_SOURCE_OPERATOR)
                    self.assertEqual(res_reset.reason, Reason.RESET_ACCEPTED)
                    self.assertEqual(res_reset.state.mode, Mode.RUN)

                    for post_tick in range(20):
                        res_post = _step_tick()
                        self.assertEqual(
                            res_post.state.mode,
                            Mode.RUN,
                            f"Post-reset trip ({res_post.reason}) at period={period_ms}ms "
                            f"phase={phase_ms}ms tick={post_tick}",
                        )
                        self.assertEqual(res_post.reason, Reason.PASS)
                        self.assertGreater(res_post.cmd_left_urad_s, 0)
                finally:
                    if rx is not None:
                        rx.close()
                    test_sock.close()
                    sender.close()

    def test_hsr_required_fails_closed_when_stale_or_missing(self) -> None:
        """When hsr_required=True, missing or stale (>96ms) HSR heartbeats trip the gate."""
        params_req = get_live_gate_params(lidar_n_expected=5, hsr_required=True)
        ranges = [2.0, 2.0, 2.0, 2.0, 2.0]
        prop = twist_to_proposal(1, 100_000, 0.20, 0.0)

        res_missing = step(initial_state(), params_req, GateInputs(
            sim_time_us=100_000,
            proposal=prop,
            ranges_m=ranges,
            lidar_stamp_us=100_000,
            hsr_status=None,
            hsr_stamp_us=None,
        ))
        self.assertEqual(res_missing.state.mode, Mode.TRIPPED)
        self.assertEqual(res_missing.reason, Reason.TRIP_HSR_INVALID)

        res_stale = step(initial_state(), params_req, GateInputs(
            sim_time_us=300_000,
            proposal=prop,
            ranges_m=ranges,
            lidar_stamp_us=300_000,
            hsr_status="CLEAR",
            hsr_stamp_us=100_000,
        ))
        self.assertEqual(res_stale.state.mode, Mode.TRIPPED)
        self.assertEqual(res_stale.reason, Reason.TRIP_HSR_STALE)

    def test_hsr_receiver_frozen_frame_trips_gate_core(self) -> None:
        """Verifies that a repeated obs_id triggers sticky freeze and trips gate fail-closed."""
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(test_sock.close)
        test_sock.setblocking(False)
        test_sock.bind(("127.0.0.1", 0))
        port = test_sock.getsockname()[1]

        rx = HsrReceiver(port=port, enabled=True, sock=test_sock)
        self.addCleanup(rx.close)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sender.close)

        params = get_live_gate_params(lidar_n_expected=5, hsr_required=True)
        prop = twist_to_proposal(1, 100_000, 0.20, 0.0)

        p_init = json.dumps({
            "obs_id": 10,
            "t_obs_us": 100_000,
            "t_emit_us": 101_000,
            "distress_permille": 0,
            "state": "CLEAR",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        }).encode("utf-8")
        sender.sendto(p_init, ("127.0.0.1", port))

        status, stamp = rx.poll(now_us=102_000)
        self.assertEqual(status, "CLEAR")
        self.assertEqual(stamp, 100_000)

        p_frozen = json.dumps({
            "obs_id": 10,
            "t_obs_us": 132_000,
            "t_emit_us": 133_000,
            "distress_permille": 0,
            "state": "CLEAR",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        }).encode("utf-8")
        sender.sendto(p_frozen, ("127.0.0.1", port))

        status, stamp = rx.poll(now_us=134_000)
        self.assertIsNone(status)
        self.assertIsNone(stamp)
        self.assertTrue(rx.frozen_latched)

        res = step(initial_state(), params, GateInputs(
            sim_time_us=134_000,
            proposal=prop,
            ranges_m=[2.0] * 5,
            lidar_stamp_us=134_000,
            hsr_status=status,
            hsr_stamp_us=stamp,
        ))
        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.reason, Reason.TRIP_HSR_INVALID)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)

    def test_hsr_receiver_producer_restart_dwell(self) -> None:
        """Verifies that counter regression triggers rebase dwell requiring 5 distinct ticks."""
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(test_sock.close)
        test_sock.setblocking(False)
        test_sock.bind(("127.0.0.1", 0))
        port = test_sock.getsockname()[1]

        rx = HsrReceiver(port=port, enabled=True, sock=test_sock)
        self.addCleanup(rx.close)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sender.close)

        p_init = json.dumps({
            "obs_id": 100,
            "t_obs_us": 100_000,
            "t_emit_us": 101_000,
            "distress_permille": 0,
            "state": "CLEAR",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        }).encode("utf-8")
        sender.sendto(p_init, ("127.0.0.1", port))
        status, _ = rx.poll(now_us=102_000)
        self.assertEqual(status, "CLEAR")

        p_rst = json.dumps({
            "obs_id": 0,
            "t_obs_us": 132_000,
            "t_emit_us": 133_000,
            "distress_permille": 0,
            "state": "CLEAR",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        }).encode("utf-8")
        sender.sendto(p_rst, ("127.0.0.1", port))
        status, _ = rx.poll(now_us=134_000)
        self.assertIsNone(status)
        self.assertTrue(rx.rebase_in_progress)

        for i in (1, 2, 3):
            p = json.dumps({
                "obs_id": i,
                "t_obs_us": 164_000,
                "t_emit_us": 165_000,
                "distress_permille": 0,
                "state": "CLEAR",
                "hazard_proximity": False,
                "persons_nearby_count": 2,
            }).encode("utf-8")
            sender.sendto(p, ("127.0.0.1", port))
        status, _ = rx.poll(now_us=166_000)
        self.assertEqual(rx.rebase_streak, 1)
        self.assertIsNone(status)

        for i in range(2, 5):
            t_sim = 164_000 + i * 32_000
            p = json.dumps({
                "obs_id": 3 + i,
                "t_obs_us": t_sim,
                "t_emit_us": t_sim + 1_000,
                "distress_permille": 0,
                "state": "CLEAR",
                "hazard_proximity": False,
                "persons_nearby_count": 2,
            }).encode("utf-8")
            sender.sendto(p, ("127.0.0.1", port))
            status, _ = rx.poll(now_us=t_sim + 2_000)
            self.assertEqual(rx.rebase_streak, i)
            self.assertIsNone(status)

        t_fin = 164_000 + 5 * 32_000
        p_fin = json.dumps({
            "obs_id": 8,
            "t_obs_us": t_fin,
            "t_emit_us": t_fin + 1_000,
            "distress_permille": 0,
            "state": "CLEAR",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        }).encode("utf-8")
        sender.sendto(p_fin, ("127.0.0.1", port))
        status, stamp = rx.poll(now_us=t_fin + 2_000)
        self.assertFalse(rx.rebase_in_progress)
        self.assertEqual(status, "CLEAR")
        self.assertEqual(stamp, t_fin)


if __name__ == "__main__":
    unittest.main()
