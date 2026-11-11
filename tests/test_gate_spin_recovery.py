# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Unit tests verifying Option A symmetrical fail-closed clamping for in-place spins.

Validates that when an untrusted proposer commands maneuvers requiring negative wheel
rotation without rearward sensor coverage (pure in-place yaw spins, reverse proposals,
or tight turns requiring an inner-wheel reversal), the Gate core clamps both wheels
to (0, 0) fail-closed, strictly preserving Rule AR-2 and preventing forward drift.
"""
from __future__ import annotations

import unittest
from typing import Tuple

from gate.gate_config import get_live_gate_params
from gate.gate_core import (
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
from ros2.qerra_gate_node import (
    DEFAULT_LIDAR_N_EXPECTED,
    DEFAULT_TRACK_WIDTH_M,
    DEFAULT_WHEEL_RADIUS_M,
    twist_to_proposal,
    twist_to_wheel_speeds,
    wheel_speeds_to_twist,
)


class TestGateSpinRecoveryKinematics(unittest.TestCase):
    """Verifies Option A symmetrical fail-closed clamping on negative wheel proposals."""

    def setUp(self) -> None:
        self.params: GateParams = get_live_gate_params(
            lidar_n_expected=DEFAULT_LIDAR_N_EXPECTED,
            wheel_radius_mm=int(round(DEFAULT_WHEEL_RADIUS_M * 1000)),
            hsr_required=False,
            t_react_us=96_000,
            lidar_period_us=32_000,
            t_stale_us=96_000,
        )
        self.clear_ranges = [3.0] * DEFAULT_LIDAR_N_EXPECTED

    def _bring_gate_to_run(self, initial_sim_time_us: int = 1_000_000) -> Tuple[GateState, int]:
        """Drives the pure gate core through startup dwell and operator reset into Mode.RUN."""
        state = initial_state()
        t = initial_sim_time_us

        # 1. Feed continuous clear dwell (1.0 s)
        for _ in range(35):
            t += 32_000
            nominal_proposal = twist_to_proposal(seq=1, sim_stamp_us=t, linear_x_mps=0.20, angular_z_radps=0.0)
            inputs = GateInputs(
                sim_time_us=t,
                proposal=nominal_proposal,
                ranges_m=self.clear_ranges,
                lidar_stamp_us=t,
            )
            result = step(state, self.params, inputs)
            state = result.state

        self.assertEqual(state.mode, Mode.AWAITING_RESET)

        # 2. Operator reset tick (quiescent command)
        t += 32_000
        nominal_proposal = twist_to_proposal(seq=2, sim_stamp_us=t, linear_x_mps=0.20, angular_z_radps=0.0)
        inputs = GateInputs(
            sim_time_us=t,
            proposal=nominal_proposal,
            ranges_m=self.clear_ranges,
            lidar_stamp_us=t,
            reset_source=RESET_SOURCE_OPERATOR,
        )
        result = step(state, self.params, inputs)
        state = result.state
        self.assertEqual(state.mode, Mode.RUN)
        self.assertEqual(result.reason, Reason.RESET_ACCEPTED)

        return state, t

    def test_01_in_place_spin_translation_produces_negative_wheel_velocity(self) -> None:
        """
        Pure yaw spin (vx=0.0, wz=0.5 rad/s) requires differential opposite wheel speeds.
        Left wheel must be negative (-0.1011 m/s), right wheel positive (+0.1011 m/s).
        """
        target_vx = 0.0
        target_wz = 0.50

        w_left_urad_s, w_right_urad_s = twist_to_wheel_speeds(
            linear_x_mps=target_vx,
            angular_z_radps=target_wz,
            track_width_m=DEFAULT_TRACK_WIDTH_M,
            wheel_radius_m=DEFAULT_WHEEL_RADIUS_M,
        )

        self.assertLess(w_left_urad_s, 0)
        self.assertGreater(w_right_urad_s, 0)
        self.assertEqual(w_left_urad_s, -1_031_633)
        self.assertEqual(w_right_urad_s, 1_031_633)

    def test_02_pure_reverse_proposal_clamps_symmetrically_to_standstill(self) -> None:
        """
        Pure reverse translation (vx=-0.20, wz=0.0) produces negative commands on BOTH wheels.
        Under Option A, both wheels clamp to 0, producing a safe stationary standstill.
        """
        state, t = self._bring_gate_to_run()

        t += 32_000
        reverse_proposal = twist_to_proposal(seq=10, sim_stamp_us=t, linear_x_mps=-0.20, angular_z_radps=0.0)
        inputs = GateInputs(
            sim_time_us=t,
            proposal=reverse_proposal,
            ranges_m=self.clear_ranges,
            lidar_stamp_us=t,
        )
        result = step(state, self.params, inputs)

        # Both wheels clamped to 0
        self.assertEqual(result.cmd_left_urad_s, 0)
        self.assertEqual(result.cmd_right_urad_s, 0)

        # Reconstructed twist is exactly stationary
        reconstructed_vx, reconstructed_wz = wheel_speeds_to_twist(
            result.cmd_left_urad_s,
            result.cmd_right_urad_s,
            track_width_m=DEFAULT_TRACK_WIDTH_M,
            wheel_radius_m=DEFAULT_WHEEL_RADIUS_M,
        )
        self.assertAlmostEqual(reconstructed_vx, 0.0, places=6)
        self.assertAlmostEqual(reconstructed_wz, 0.0, places=6)

    def test_03_in_place_spin_is_clamped_fail_closed_to_zero_preventing_forward_drift(self) -> None:
        """
        VERIFICATION OF OPTION A FAIL-CLOSED SPIN PROTECTION:
        When an untrusted proposer requests an in-place spin (vx=0.0, wz=0.5 rad/s) without
        rearward sensor coverage, the gate core detects that the left wheel requires negative
        rotation (w_left = -1_031_633 urad/s) and clamps BOTH wheels to (0, 0).
        This eliminates the unintended forward translation and preserves Rule AR-2 (vx_out <= vx_prop).
        """
        state, t = self._bring_gate_to_run()

        target_vx = 0.0
        target_wz = 0.50

        t += 32_000
        spin_proposal = twist_to_proposal(
            seq=10,
            sim_stamp_us=t,
            linear_x_mps=target_vx,
            angular_z_radps=target_wz,
            track_width_m=DEFAULT_TRACK_WIDTH_M,
            wheel_radius_m=DEFAULT_WHEEL_RADIUS_M,
        )
        inputs = GateInputs(
            sim_time_us=t,
            proposal=spin_proposal,
            ranges_m=self.clear_ranges,
            lidar_stamp_us=t,
        )
        result = step(state, self.params, inputs)

        # Option A invariant: Both wheels are held at 0 fail-closed
        self.assertEqual(result.cmd_left_urad_s, 0)
        self.assertEqual(result.cmd_right_urad_s, 0)

        # Reconstructed body twist holds exact standstill
        reconstructed_vx, reconstructed_wz = wheel_speeds_to_twist(
            result.cmd_left_urad_s,
            result.cmd_right_urad_s,
            track_width_m=DEFAULT_TRACK_WIDTH_M,
            wheel_radius_m=DEFAULT_WHEEL_RADIUS_M,
        )

        # Invariant checks:
        self.assertAlmostEqual(reconstructed_vx, 0.0, places=6)
        self.assertAlmostEqual(reconstructed_wz, 0.0, places=6)
        self.assertLessEqual(reconstructed_vx, target_vx)  # AR-2 preserved

    def test_04_tight_turn_with_negative_inner_wheel_is_clamped_to_standstill(self) -> None:
        """
        VERIFICATION OF OPTION A SPEED BOOST PREVENTION:
        When a tight forward turn requires a negative inner wheel (vx=0.05 m/s, wz=0.5 rad/s,
        where inner wheel w_left < 0), Option A clamps BOTH wheels to (0, 0) rather than allowing
        the outer wheel to accelerate the robot forward into unmonitored space.
        """
        target_vx = 0.05
        target_wz = 0.50

        w_left_urad_s, w_right_urad_s = twist_to_wheel_speeds(
            linear_x_mps=target_vx,
            angular_z_radps=target_wz,
            track_width_m=DEFAULT_TRACK_WIDTH_M,
            wheel_radius_m=DEFAULT_WHEEL_RADIUS_M,
        )

        self.assertLess(w_left_urad_s, 0)
        self.assertGreater(w_right_urad_s, 0)

        state, t = self._bring_gate_to_run()
        t += 32_000
        tight_turn_proposal = Proposal(
            seq=10,
            sim_stamp_us=t,
            left_urad_s=w_left_urad_s,
            right_urad_s=w_right_urad_s,
            session_id=1,
        )
        inputs = GateInputs(
            sim_time_us=t,
            proposal=tight_turn_proposal,
            ranges_m=self.clear_ranges,
            lidar_stamp_us=t,
        )
        result = step(state, self.params, inputs)

        # Option A invariant: Symmetrical clamp to (0, 0)
        self.assertEqual(result.cmd_left_urad_s, 0)
        self.assertEqual(result.cmd_right_urad_s, 0)

        reconstructed_vx, _ = wheel_speeds_to_twist(
            result.cmd_left_urad_s,
            result.cmd_right_urad_s,
            track_width_m=DEFAULT_TRACK_WIDTH_M,
            wheel_radius_m=DEFAULT_WHEEL_RADIUS_M,
        )

        # Invariant checks:
        self.assertAlmostEqual(reconstructed_vx, 0.0, places=6)
        self.assertLessEqual(reconstructed_vx, target_vx)  # AR-2 preserved (never accelerated)


if __name__ == "__main__":
    unittest.main()
