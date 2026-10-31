# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""Wiring checks for the QERRA ROS 2 gate node that run on hosts without rclpy."""
from __future__ import annotations

import json
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
from ros2.qerra_gate_node import (
    DEFAULT_LIDAR_N_EXPECTED,
    DEFAULT_WHEEL_RADIUS_M,
    format_gate_state_json,
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
        # The Webots controller passes these two explicitly; the node relies on defaults.
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


if __name__ == "__main__":
    unittest.main()
