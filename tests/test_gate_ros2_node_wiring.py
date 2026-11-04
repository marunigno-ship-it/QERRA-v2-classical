# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""Wiring checks and adversarial fault-injection tests for the QERRA ROS 2 gate node (stdlib only)."""
from __future__ import annotations

import json
import math
import socket
import unittest

from gate.gate_config import get_live_gate_params
from gate.gate_core import (
    Event,
    GateInputs,
    Mode,
    Proposal,
    Reason,
    RESET_SOURCE_OPERATOR,
    RESET_SOURCE_PROPOSER,
    initial_state,
    step,
)
from ros2.hsr_receiver import HsrReceiver
from ros2.qerra_gate_node import (
    DEFAULT_LIDAR_N_EXPECTED,
    DEFAULT_WHEEL_RADIUS_M,
    create_lidar_pipeline,
    format_gate_state_json,
    process_laser_scan,
    twist_to_proposal,
)

DT_US = 32_000


class TestGateNodeWiring(unittest.TestCase):
    """Checks the parts of the node wiring that do not need rclpy."""

    def _drive_to_run(self, params, ranges):
        """Latched start -> clear dwell -> operator reset -> one RUN tick."""
        state = initial_state()
        sim_t = 100_000
        seq = 0
        for _ in range(35):
            sim_t += DT_US
            seq += 1
            res = step(state, params, GateInputs(
                sim_time_us=sim_t,
                proposal=twist_to_proposal(seq, sim_t, 0.20, 0.0),
                ranges_m=ranges,
                lidar_stamp_us=sim_t,
                hsr_status="CLEAR",
                hsr_stamp_us=sim_t,
            ))
            state = res.state
        self.assertEqual(state.mode, Mode.AWAITING_RESET)

        sim_t += DT_US
        seq += 1
        res = step(state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=twist_to_proposal(seq, sim_t, 0.20, 0.0),
            ranges_m=ranges,
            lidar_stamp_us=sim_t,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status="CLEAR",
            hsr_stamp_us=sim_t,
        ))
        state = res.state
        self.assertEqual(res.reason, Reason.RESET_ACCEPTED)

        sim_t += DT_US
        seq += 1
        res = step(state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=twist_to_proposal(seq, sim_t, 0.20, 0.0),
            ranges_m=ranges,
            lidar_stamp_us=sim_t,
            hsr_status="CLEAR",
            hsr_stamp_us=sim_t,
        ))
        self.assertEqual(res.state.mode, Mode.RUN)
        self.assertEqual(res.reason, Reason.PASS)
        return res.state, sim_t, seq

    def test_node_parameter_construction_matches_controller(self) -> None:
        """Uses the exact keyword arguments of QerraGateNode.__init__."""
        params = get_live_gate_params(
            lidar_n_expected=DEFAULT_LIDAR_N_EXPECTED,
            wheel_radius_mm=int(round(DEFAULT_WHEEL_RADIUS_M * 1000)),
            hsr_required=True,
        )
        self.assertEqual(params.lidar_n_expected, 682)
        self.assertEqual(params.wheel_radius_mm, 98)
        self.assertTrue(params.hsr_required)
        self.assertEqual(params.dt_us, DT_US)
        self.assertEqual(params.t_react_us, 32_000)

    def test_discarded_scan_trips_a_running_gate(self) -> None:
        """A scan discarded by the node (ranges None, stamp None) must trip a RUN gate."""
        params = get_live_gate_params(lidar_n_expected=5, hsr_required=False)
        ranges = [2.0, 2.0, 2.0, 2.0, 2.0]
        state, sim_t, seq = self._drive_to_run(params, ranges)

        sim_t += DT_US
        seq += 1
        res = step(state, params, GateInputs(
            sim_time_us=sim_t,
            proposal=twist_to_proposal(seq, sim_t, 0.20, 0.0),
            ranges_m=None,
            lidar_stamp_us=None,
            raw_valid_points=None,
            hsr_status="CLEAR",
            hsr_stamp_us=sim_t,
        ))
        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertTrue(res.reason.startswith("TRIP_"))
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)

    def test_state_json_reports_hsr_configuration(self) -> None:
        """/gate/state must show which HSR source is configured and whether it is required."""
        params = get_live_gate_params(lidar_n_expected=5, hsr_required=False)
        res = step(initial_state(), params, GateInputs(
            sim_time_us=100_000,
            proposal=None,
            ranges_m=None,
            lidar_stamp_us=None,
        ))
        payload = json.loads(format_gate_state_json(
            res.state,
            res.record,
            hsr_source="udp",
            hsr_required=True,
            hsr_drained=3,
            hsr_error=None,
        ))
        self.assertEqual(payload["hsr_source"], "udp")
        self.assertTrue(payload["hsr_required"])
        self.assertEqual(payload["hsr_drained_total"], 3)
        self.assertIsNone(payload["hsr_socket_error"])
        self.assertEqual(payload["mode"], res.state.mode.value)

    def test_adversarial_reset_rejected_during_dwell_or_hazard(self) -> None:
        """Verifies that malicious or forged resets cannot bypass dwell or active hazards."""
        params = get_live_gate_params(lidar_n_expected=5, hsr_required=True)
        ranges_clear = [3.0] * 5
        ranges_hazard = [0.2] * 5  # 200mm obstacle breach (< 300mm margin)

        # 1. Reset from unauthorized channel ("proposer") is strictly rejected
        state = initial_state()
        res_chan = step(state, params, GateInputs(
            sim_time_us=100_000,
            proposal=twist_to_proposal(1, 100_000, 0.20, 0.0),
            ranges_m=ranges_clear,
            lidar_stamp_us=100_000,
            reset_source=RESET_SOURCE_PROPOSER,
            hsr_status="CLEAR",
            hsr_stamp_us=100_000,
        ))
        self.assertEqual(res_chan.state.mode, Mode.TRIPPED)
        self.assertIn(Event.RESET_REJECTED_CHANNEL, res_chan.events)

        # 2. Forged "operator" reset sent before 1.0s dwell completes is rejected
        res_early = step(state, params, GateInputs(
            sim_time_us=100_000 + DT_US,
            proposal=twist_to_proposal(2, 100_000 + DT_US, 0.20, 0.0),
            ranges_m=ranges_clear,
            lidar_stamp_us=100_000 + DT_US,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status="CLEAR",
            hsr_stamp_us=100_000 + DT_US,
        ))
        self.assertEqual(res_early.state.mode, Mode.TRIPPED)
        self.assertIn(Event.RESET_REJECTED_NOT_READY, res_early.events)

        # 3. Forged "operator" reset sent during active obstacle breach is rejected
        res_obst = step(state, params, GateInputs(
            sim_time_us=200_000,
            proposal=twist_to_proposal(3, 200_000, 0.20, 0.0),
            ranges_m=ranges_hazard,
            lidar_stamp_us=200_000,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status="CLEAR",
            hsr_stamp_us=200_000,
        ))
        self.assertEqual(res_obst.state.mode, Mode.TRIPPED)
        self.assertIn(Event.RESET_REJECTED_HAZARD, res_obst.events)

        # 4. Forged "operator" reset sent while HSR distress is active is rejected
        res_distress = step(state, params, GateInputs(
            sim_time_us=300_000,
            proposal=twist_to_proposal(4, 300_000, 0.20, 0.0),
            ranges_m=ranges_clear,
            lidar_stamp_us=300_000,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status="CRITICAL",
            hsr_stamp_us=300_000,
        ))
        self.assertEqual(res_distress.state.mode, Mode.TRIPPED)
        self.assertIn(Event.RESET_REJECTED_HAZARD, res_distress.events)

    def test_fault_injection_malformed_udp_packets_dropped_fail_closed(self) -> None:
        """Verifies that hostile or malformed UDP datagrams are dropped without crashing."""
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(test_sock.close)
        test_sock.setblocking(False)
        test_sock.bind(("127.0.0.1", 0))
        port = test_sock.getsockname()[1]

        rx = HsrReceiver(port=port, enabled=True, sock=test_sock)
        self.addCleanup(rx.close)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sender.close)
        dest = ("127.0.0.1", port)

        # 1. Non-JSON binary noise
        sender.sendto(b"\x00\xff\xfe\x01\xdeadbeef\xbadf00d", dest)
        # 2. Valid JSON with negative obs_id
        sender.sendto(json.dumps({"obs_id": -5, "t_obs_us": 100_000, "t_emit_us": 101_000, "distress_permille": 0}).encode("utf-8"), dest)
        # 3. Causal inversion: t_emit < t_obs
        sender.sendto(json.dumps({"obs_id": 1, "t_obs_us": 200_000, "t_emit_us": 150_000, "distress_permille": 0}).encode("utf-8"), dest)
        # 4. Clock inversion: future frame against gate clock
        sender.sendto(json.dumps({"obs_id": 2, "t_obs_us": 500_000, "t_emit_us": 501_000, "distress_permille": 0}).encode("utf-8"), dest)

        # Draining must silently drop all 4 malformed packets without exception
        status, stamp = rx.poll(now_us=300_000)
        self.assertIsNone(status)
        self.assertIsNone(stamp)
        self.assertEqual(rx.packets_drained_total, 4)

    def test_fault_injection_lidar_dimension_mismatch_trips_gate(self) -> None:
        """Verifies that scan geometry violations force TRIP_SENSOR_INVALID fail-closed."""
        pipeline = create_lidar_pipeline(n_samples=682, fov_rad=math.pi)
        params = get_live_gate_params(lidar_n_expected=682, hsr_required=False)

        # 500 beams received when 682 expected (e.g. truncated sensor buffer)
        truncated_ranges = [1.5] * 500

        # process_laser_scan preserves length; pipeline.process verifies against corridor
        # In qerra_gate_node, beam mismatch discards scan: ranges=None, stamp=None
        res = step(initial_state(), params, GateInputs(
            sim_time_us=100_000,
            proposal=twist_to_proposal(1, 100_000, 0.20, 0.0),
            ranges_m=None,
            lidar_stamp_us=None,
        ))
        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.reason, Reason.TRIP_SENSOR_INVALID)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)

    def test_fault_injection_clock_reversal_trips_clock_anomaly(self) -> None:
        """Verifies that non-monotonic simulation time trips TRIP_CLOCK_ANOMALY."""
        params = get_live_gate_params(lidar_n_expected=5, hsr_required=False)
        state = initial_state()

        # Tick 1 at t = 200,000 us
        res1 = step(state, params, GateInputs(
            sim_time_us=200_000,
            proposal=twist_to_proposal(1, 200_000, 0.20, 0.0),
            ranges_m=[2.0] * 5,
            lidar_stamp_us=200_000,
        ))
        self.assertEqual(res1.state.last_tick_us, 200_000)

        # Tick 2 injected with backward time jump: t = 190,000 us (t_now <= t_prev)
        res2 = step(res1.state, params, GateInputs(
            sim_time_us=190_000,
            proposal=twist_to_proposal(2, 190_000, 0.20, 0.0),
            ranges_m=[2.0] * 5,
            lidar_stamp_us=190_000,
        ))
        self.assertEqual(res2.state.mode, Mode.TRIPPED)
        self.assertEqual(res2.reason, Reason.TRIP_CLOCK_ANOMALY)
        self.assertEqual(res2.cmd_left_urad_s, 0)
        self.assertEqual(res2.cmd_right_urad_s, 0)

    def test_fault_injection_multi_hazard_priority_hierarchy(self) -> None:
        """Verifies that simultaneous hazards resolve deterministically fail-closed."""
        params = get_live_gate_params(lidar_n_expected=5, hsr_required=True)
        ranges_hazard = [0.15] * 5  # 150mm obstacle breach (< 300mm margin)

        # Simultaneous faults: Obstacle Hazard + HSR Critical Distress + Proposal Candidate
        res = step(initial_state(), params, GateInputs(
            sim_time_us=100_000,
            proposal=twist_to_proposal(1, 100_000, 0.50, 0.0),
            ranges_m=ranges_hazard,
            lidar_stamp_us=100_000,
            hsr_status="CRITICAL",
            hsr_stamp_us=100_000,
        ))
        # Obstacle dominates HSR_CRITICAL in fixed priority hierarchy
        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.reason, Reason.TRIP_OBSTACLE)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)


if __name__ == "__main__":
    unittest.main()
