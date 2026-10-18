# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
Unit tests for gate/gate_config.py live parameter factory (F4 / V3).
Verifies that live deployment parameters include reaction time (t_react_us > 0),
that stopping distance envelope grows as derived, and that controller imports it.
Standard library only.
"""
from __future__ import annotations

import os
import unittest

from gate.gate_config import DEFAULT_LIVE_T_REACT_US, get_live_gate_params
from gate.gate_core import d_stop_mm, wheel_to_mmps


class TestGateConfig(unittest.TestCase):
    def test_live_params_reaction_time_is_active(self):
        """F4 / V3: live parameters must not default t_react_us to 0."""
        params = get_live_gate_params(lidar_n_expected=5)
        self.assertGreater(params.t_react_us, 0)
        self.assertEqual(params.t_react_us, DEFAULT_LIVE_T_REACT_US)
        self.assertEqual(params.t_react_us, 32_000)

    def test_live_params_stopping_envelope_growth(self):
        """
        Derivation:
          v = 196 mm/s (cruise speed at 2.0 rad/s with 98 mm wheel)
          braking = ceil(196^2 / (2 * 500)) = 39 mm
          reaction = ceil(196 * 32_000 / 1_000_000) = ceil(6.272) = 7 mm
          margin = 300 mm
          baseline (t_react=0) = 339 mm
          live (t_react=32_000) = 346 mm (+7 mm growth)
        """
        params_live = get_live_gate_params(lidar_n_expected=5, t_react_us=32_000)
        v = wheel_to_mmps(params_live, 2_000_000)
        self.assertEqual(v, 196)

        stop_live = d_stop_mm(params_live, v)
        self.assertEqual(stop_live, 346)

        # Confirm exact 7 mm growth over t_react_us=0
        params_zero = get_live_gate_params(lidar_n_expected=5, t_react_us=0)
        stop_zero = d_stop_mm(params_zero, v)
        self.assertEqual(stop_zero, 339)
        self.assertEqual(stop_live - stop_zero, 7)

    def test_live_params_preserves_safety_invariants(self):
        """Live factory must preserve all established safety parameters."""
        p = get_live_gate_params(lidar_n_expected=5)
        self.assertEqual(p.dt_us, 32_000)
        self.assertEqual(p.t_watch_us, 150_000)
        self.assertEqual(p.margin_mm, 300)
        self.assertEqual(p.a_design_mmps2, 500)
        self.assertEqual(p.t_dwell_us, 1_000_000)
        self.assertEqual(p.min_raw_lidar_returns, 5)

    def test_tiago_controller_uses_live_parameter_factory(self):
        """Controller source must instantiate parameters via get_live_gate_params (F4)."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        controller_path = os.path.join(
            project_root, "controllers", "tiago_supervisory_gate", "tiago_supervisory_gate.py"
        )
        with open(controller_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn(
            "get_live_gate_params",
            source,
            "Controller must import and call get_live_gate_params to ensure F4 reaction time is live",
        )


if __name__ == "__main__":
    unittest.main()
