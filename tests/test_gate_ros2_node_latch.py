# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""Unit tests for QERRA ROS 2 gate node fault latch and telemetry formatting (stdlib only)."""
from __future__ import annotations

import json
import unittest

from gate.gate_core import initial_state
from ros2.qerra_gate_node import (
    NodeFaultLatch,
    format_gate_state_json,
)


class TestNodeFaultLatch(unittest.TestCase):
    """Verifies fail-closed persistent latching logic."""

    def test_fresh_latch_is_not_latched_and_has_no_reason(self) -> None:
        """A freshly initialized latch is open (unlatched) with no error reason."""
        latch = NodeFaultLatch()
        self.assertFalse(latch.is_latched)
        self.assertIsNone(latch.fault_reason)

    def test_trip_with_exception_latches_with_reason(self) -> None:
        """Tripping the latch with an exception records the string representation."""
        latch = NodeFaultLatch()
        latch.trip(ValueError("x"))
        self.assertTrue(latch.is_latched)
        self.assertEqual(latch.fault_reason, "x")

    def test_second_trip_keeps_first_reason(self) -> None:
        """Subsequent trips do not overwrite the initial root-cause reason."""
        latch = NodeFaultLatch()
        latch.trip("first fault")
        latch.trip("second fault")
        self.assertTrue(latch.is_latched)
        self.assertEqual(latch.fault_reason, "first fault")

    def test_whitespace_reason_becomes_unknown_node_fault(self) -> None:
        """Tripping with empty or whitespace string defaults to 'Unknown node fault'."""
        latch_ws = NodeFaultLatch()
        latch_ws.trip("   ")
        self.assertTrue(latch_ws.is_latched)
        self.assertEqual(latch_ws.fault_reason, "Unknown node fault")

        latch_empty = NodeFaultLatch()
        latch_empty.trip("")
        self.assertTrue(latch_empty.is_latched)
        self.assertEqual(latch_empty.fault_reason, "Unknown node fault")


class TestFormatGateStateJsonLatch(unittest.TestCase):
    """Verifies JSON telemetry formatting under normal and latched fault states."""

    def test_format_gate_state_json_latched_forces_fault_mode_and_zero_commands(self) -> None:
        """
        When fault_latched=True, telemetry forces mode 'FAULT', prefixes the reason with
        'NODE_FAULT_LATCHED: ', forces both wheel speeds to 0 urad/s, and echoes the fault reason.
        """
        state = initial_state()
        mock_record = {
            "reason": "PASS",
            "d_stop_mm": 300,
            "lidar_min_mm": 500.0,
            "hsr_status": "CLEAR",
            "proposal_seq": 42,
            "proposal_age_us": 1500,
            "cmd_left_urad_s": 2_040_816,
            "cmd_right_urad_s": 2_040_816,
        }

        payload_str = format_gate_state_json(
            state,
            mock_record,
            fault_latched=True,
            fault_reason="hardware timer drift",
        )
        data = json.loads(payload_str)

        self.assertEqual(data["mode"], "FAULT")
        self.assertEqual(data["reason"], "NODE_FAULT_LATCHED: hardware timer drift")
        self.assertTrue(data["fault_latched"])
        self.assertEqual(data["fault_reason"], "hardware timer drift")
        self.assertEqual(data["cmd_left_urad_s"], 0)
        self.assertEqual(data["cmd_right_urad_s"], 0)
        self.assertEqual(data["d_stop_mm"], 300)

    def test_format_gate_state_json_unlatched_preserves_state_and_commands(self) -> None:
        """When fault_latched=False, telemetry reflects gate core state and records commands."""
        state = initial_state()
        mock_record = {
            "reason": "PASS",
            "d_stop_mm": 450,
            "lidar_min_mm": 1200.0,
            "hsr_status": "CLEAR",
            "proposal_seq": 10,
            "proposal_age_us": 800,
            "cmd_left_urad_s": 2_040_816,
            "cmd_right_urad_s": 2_040_816,
        }

        payload_str = format_gate_state_json(
            state,
            mock_record,
            fault_latched=False,
            fault_reason=None,
        )
        data = json.loads(payload_str)

        self.assertEqual(data["mode"], state.mode.value)
        self.assertEqual(data["reason"], "PASS")
        self.assertFalse(data["fault_latched"])
        self.assertIsNone(data["fault_reason"])
        self.assertEqual(data["cmd_left_urad_s"], 2_040_816)
        self.assertEqual(data["cmd_right_urad_s"], 2_040_816)


if __name__ == "__main__":
    unittest.main()
