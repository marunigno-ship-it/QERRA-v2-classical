# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""Unit tests for QERRA ROS 2 gate node translators and HSR reflex receiver (stdlib only)."""
from __future__ import annotations

import json
import math
import socket
import unittest

from gate.gate_config import get_live_gate_params
from gate.gate_core import (
    GateInputs,
    Mode,
    Reason,
    RESET_SOURCE_OPERATOR,
    initial_state,
    step,
)
from ros2.hsr_receiver import HsrReceiver
from ros2.qerra_gate_node import (
    DEFAULT_TRACK_WIDTH_M,
    DEFAULT_WHEEL_RADIUS_M,
    DEFAULT_ROBOT_HALF_WIDTH_M,
    NODE_VERSION,
    ROS2_AVAILABLE,
    create_lidar_pipeline,
    process_laser_scan,
    require_ros2,
    twist_to_proposal,
    twist_to_wheel_speeds,
    wheel_speeds_to_twist,
)


class TestGateRos2Translators(unittest.TestCase):
    """Verifies kinematic and lidar translators for the QERRA ROS 2 gate node."""

    def test_version_and_import_guard(self) -> None:
        """Confirms node metadata and that require_ros2 fails loudly on Windows."""
        self.assertEqual(NODE_VERSION, "0.3.0")
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


class TestHsrReceiverAndReflexIntegration(unittest.TestCase):
    """Verifies HSR UDP reflex receiver and Layer 1B trip enforcement in gate core."""

    def test_hsr_receiver_disabled_returns_none(self) -> None:
        """When HSR source is disabled, poll always returns (None, None)."""
        rx = HsrReceiver(enabled=False)
        self.addCleanup(rx.close)
        status, stamp = rx.poll(now_us=100_000)
        self.assertIsNone(status)
        self.assertIsNone(stamp)

    def test_hsr_receiver_udp_distress_trips_gate_core(self) -> None:
        """
        Recovery from a latched trip, then acute distress (CRITICAL) via UDP trips the gate.

        Gate Core v0.4 behaviour under test: on the exact tick where the operator reset is
        accepted (Reason.RESET_ACCEPTED) the mode becomes RUN but the wheels stay at zero
        (quiescent re-arm tick, no lurch on the reset command). Motion resumes on the next
        RUN tick (Reason.PASS).
        """
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # HsrReceiver does not close a socket that was handed to it, so the test owns it.
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

        # Send initial CLEAR datagram
        clear_payload = json.dumps({
            "obs_id": 1,
            "t_obs_us": 100_000,
            "t_emit_us": 101_000,
            "distress_permille": 0,
            "state": "CLEAR",
        }).encode("utf-8")
        sender.sendto(clear_payload, ("127.0.0.1", port))

        sim_t = 100_000
        status, stamp = rx.poll(now_us=sim_t)
        self.assertEqual(status, "CLEAR")
        self.assertEqual(stamp, 100_000)

        # 1. Step gate across unbroken 32ms control ticks to satisfy t_dwell_us (1.0 s)
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

        # Unbroken dwell satisfied (35 ticks * 32ms = 1.12s > 1.0s dwell)
        self.assertEqual(state.mode, Mode.AWAITING_RESET)

        # 2. Operator reset accepted -> enters RUN, wheels held at zero on this tick
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

        # 3. Next tick in RUN with fresh inputs -> motion resumes (Reason.PASS)
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

        # 4. Transmit CRITICAL distress datagram via UDP
        distress_payload = json.dumps({
            "obs_id": 2,
            "t_obs_us": sim_t + dt_us,
            "t_emit_us": sim_t + dt_us + 1_000,
            "distress_permille": 850,
            "state": "CRITICAL",
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

        # Gate must immediately trip to 0 urad/s on acute distress
        self.assertEqual(crit_res.state.mode, Mode.TRIPPED)
        self.assertEqual(crit_res.reason, Reason.TRIP_HSR_CRITICAL)
        self.assertEqual(crit_res.cmd_left_urad_s, 0)
        self.assertEqual(crit_res.cmd_right_urad_s, 0)

    def test_hsr_required_fails_closed_when_stale_or_missing(self) -> None:
        """When hsr_required=True, missing or stale (>96ms) HSR heartbeats trip the gate."""
        params_req = get_live_gate_params(lidar_n_expected=5, hsr_required=True)
        ranges = [2.0, 2.0, 2.0, 2.0, 2.0]
        prop = twist_to_proposal(1, 100_000, 0.20, 0.0)

        # 1. Missing telemetry -> TRIP_HSR_INVALID
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

        # 2. Stale heartbeat (age = 200 ms > 96 ms t_hsr_stale_us) -> TRIP_HSR_STALE
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


if __name__ == "__main__":
    unittest.main()
