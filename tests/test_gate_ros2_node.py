# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""Unit tests for QERRA ROS 2 gate node translators (stdlib only)."""
from __future__ import annotations

import math
import unittest

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
        # 5 samples over 180 degrees (-90 to +90). Center beam index 2 is forward (0 degrees).
        pipeline = create_lidar_pipeline(n_samples=5, fov_rad=math.pi, half_width_m=0.32)

        # Center obstacle at 0.5m, outer beams at 2.0m (lateral offset = 2.0 * sin(90°) = 2.0m > 0.32m)
        raw_ranges = [2.0, 1.0, 0.5, 1.0, 2.0]
        filtered, stamp_us, valid_pts = process_laser_scan(
            raw_ranges, stamp_sec=2, stamp_nanosec=250_000_000, pipeline=pipeline
        )

        self.assertEqual(stamp_us, 2_250_000)
        self.assertEqual(valid_pts, 5)
        self.assertEqual(len(filtered), 5)
        self.assertEqual(filtered[2], 0.5)  # Center beam inside corridor
        self.assertTrue(math.isinf(filtered[0]))  # Far left beam clipped to +inf
        self.assertTrue(math.isinf(filtered[4]))  # Far right beam clipped to +inf

    def test_lidar_stalled_hardware_watchdog(self) -> None:
        """When sensor acquisition stalls, the acquisition timestamp does not advance."""
        pipeline = create_lidar_pipeline(n_samples=3, fov_rad=1.0)

        _, stamp_1, _ = process_laser_scan([1.0, 1.0, 1.0], 1, 0, pipeline, stalled=False)
        self.assertEqual(stamp_1, 1_000_000)

        # Stalled read at t = 2.0s: timestamp must remain 1_000_000 to trigger t_stale trip
        _, stamp_2, _ = process_laser_scan([1.0, 1.0, 1.0], 2, 0, pipeline, stalled=True)
        self.assertEqual(stamp_2, 1_000_000)

    def test_lidar_negative_timestamp_rejected(self) -> None:
        """Rejects negative timestamp fields fail-closed."""
        pipeline = create_lidar_pipeline(n_samples=3, fov_rad=1.0)
        with self.assertRaises(ValueError):
            process_laser_scan([1.0, 1.0, 1.0], -1, 0, pipeline)
        with self.assertRaises(ValueError):
            process_laser_scan([1.0, 1.0, 1.0], 0, -500, pipeline)


if __name__ == "__main__":
    unittest.main()
