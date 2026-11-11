# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Nav2-Compatible Exterior Command-Interface Integration Tests (Pattern B).

Verifies the integration contract between an external Nav2-compatible command
source (publishing untrusted proposals to /cmd_vel_nav) and the robot base
controller (receiving verified setpoints on /base/cmd_vel).

Tests 4 distinct operational scenarios:
1. Linear Cruise & Active Topic Isolation: Unhindered forward cruise under clear corridor,
   plus active verification that proposals to default /cmd_vel are completely ignored.
2. Coordinated Arc Passthrough: Linear + angular turning proposals translated
   and reconstructed through differential kinematics.
3. Dynamic Obstacle Interception: Active motion clamped fail-closed to 0.0 m/s
   within the test polling budget upon corridor breach.
4. Proposal Stream Interruption Watchdog: Fail-closed trip (TRIP_PROPOSER_STALE)
   when velocity proposals cease while sensors remain active.

SAFETY NOTICE:
QERRA is an open-source, simulation-based research prototype with zero physical
hardware testing. A 0.0 m/s command is a software setpoint, not a hardware
emergency stop. ISO 13849-1, ISO 13482, and ISO 3691-4 are informative references.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
import unittest
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import String

    from ros2.qerra_gate_node import (
        DEFAULT_LIDAR_N_EXPECTED,
        QerraGateNode,
    )

    ROS2_AVAILABLE = True
except ImportError as exc:
    # If CI mandates ROS 2, fail loudly rather than silently skipping
    if os.environ.get("QERRA_REQUIRE_ROS2") == "1":
        raise RuntimeError(
            f"QERRA_REQUIRE_ROS2=1 is set, but ROS 2 imports failed: {exc}"
        ) from exc
    rclpy = None
    SingleThreadedExecutor = None
    Node = Any
    qos_profile_sensor_data = Any
    Twist = Any
    LaserScan = Any
    String = Any
    QerraGateNode = Any
    DEFAULT_LIDAR_N_EXPECTED = 682
    ROS2_AVAILABLE = False


if ROS2_AVAILABLE:

    class Nav2ExteriorHarnessNode(Node):
        """Harness simulating a Nav2-compatible proposer and base controller interface."""

        def __init__(self) -> None:
            super().__init__("nav2_exterior_harness_node")
            self._lock = threading.Lock()

            # Publishers targeting Pattern B exterior interface
            self.pub_nav = self.create_publisher(Twist, "/cmd_vel_nav", 10)
            self.pub_scan = self.create_publisher(LaserScan, "/scan", qos_profile_sensor_data)
            self.pub_reset = self.create_publisher(String, "/gate/reset", 10)

            # Isolation canary publisher targeting default unmapped /cmd_vel
            self.pub_default_cmd = self.create_publisher(Twist, "/cmd_vel", 10)

            # Subscribers listening to base controller topic and telemetry
            self.sub_base_cmd = self.create_subscription(
                Twist, "/base/cmd_vel", self._base_cmd_cb, 10
            )
            self.sub_default_safe = self.create_subscription(
                Twist, "/cmd_vel_safe", self._default_safe_cb, 10
            )
            self.sub_state = self.create_subscription(
                String, "/gate/state", self._state_cb, 10
            )

            self.latest_base_twist: Optional[Twist] = None
            self.latest_state_json: Optional[Dict[str, Any]] = None
            self.base_twist_count = 0
            self.default_safe_count = 0

        def _base_cmd_cb(self, msg: Twist) -> None:
            with self._lock:
                self.latest_base_twist = msg
                self.base_twist_count += 1

        def _default_safe_cb(self, _msg: Twist) -> None:
            with self._lock:
                self.default_safe_count += 1

        def _state_cb(self, msg: String) -> None:
            with self._lock:
                try:
                    self.latest_state_json = json.loads(msg.data)
                except Exception:
                    self.latest_state_json = None

        def reset_telemetry_history(self) -> None:
            """Resets recorded telemetry frames and counters between test phases."""
            with self._lock:
                self.latest_base_twist = None
                self.latest_state_json = None
                self.base_twist_count = 0
                self.default_safe_count = 0

        def get_snapshot(self) -> Tuple[Optional[Twist], Optional[Dict[str, Any]], int, int]:
            """Thread-safe snapshot of latest twist, state, and message counts."""
            with self._lock:
                return (
                    self.latest_base_twist,
                    self.latest_state_json,
                    self.base_twist_count,
                    self.default_safe_count,
                )

        def publish_nav_proposal(self, linear_x: float, angular_z: float) -> None:
            msg = Twist()
            msg.linear.x = float(linear_x)
            msg.angular.z = float(angular_z)
            self.pub_nav.publish(msg)

        def publish_default_proposal(self, linear_x: float, angular_z: float) -> None:
            msg = Twist()
            msg.linear.x = float(linear_x)
            msg.angular.z = float(angular_z)
            self.pub_default_cmd.publish(msg)

        def publish_scan(self, ranges: List[float], n_expected: int = DEFAULT_LIDAR_N_EXPECTED) -> None:
            if len(ranges) != n_expected:
                raise ValueError(f"Expected {n_expected} ranges, got {len(ranges)}")
            scan = LaserScan()
            scan.header.stamp = self.get_clock().now().to_msg()
            scan.header.frame_id = "base_laser_link"
            scan.angle_min = -2.0943951
            scan.angle_max = 2.0943951
            scan.angle_increment = 4.1887902 / float(n_expected)
            scan.time_increment = 0.0
            scan.scan_time = 0.032
            scan.range_min = 0.05
            scan.range_max = 10.0
            scan.ranges = [float(r) for r in ranges]
            self.pub_scan.publish(scan)

        def publish_reset(self, source: str = "operator") -> None:
            msg = String()
            msg.data = source
            self.pub_reset.publish(msg)


@unittest.skipUnless(ROS2_AVAILABLE, "Requires native ROS 2 (rclpy) installation")
class TestGateRos2Nav2Exterior(unittest.TestCase):
    """Verifies Nav2 Pattern B exterior command-interface integration contracts."""

    def setUp(self) -> None:
        if rclpy.ok():
            rclpy.shutdown()

        # Pattern B topic remappings:
        # cmd_vel_in  := /cmd_vel_nav (Nav2 controller output)
        # cmd_vel_out := /base/cmd_vel (Base controller input)
        rclpy.init(args=[
            "--ros-args",
            "-r", "qerra_gate_node:/cmd_vel:=/cmd_vel_nav",
            "-r", "qerra_gate_node:/cmd_vel_safe:=/base/cmd_vel",
            "-p", "hsr_required:=false",
            "-p", "hsr_source:=none",
            "-p", "flight_log_path:=none",
        ])

        self.gate_node = QerraGateNode()
        self.harness_node = Nav2ExteriorHarnessNode()

        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.gate_node)
        self.executor.add_node(self.harness_node)

        self._stop_event = threading.Event()
        self._spin_error: Optional[Exception] = None
        self._spin_thread = threading.Thread(target=self._spin_loop, daemon=True)
        self._spin_thread.start()

    def tearDown(self) -> None:
        self._stop_event.set()
        if self._spin_thread.is_alive():
            self._spin_thread.join(timeout=2.0)

        # Enforce clean thread termination without lingering execution
        if self._spin_thread.is_alive():
            self.fail("Spin thread failed to terminate within 2.0s timeout")

        self.executor.shutdown()
        self.gate_node.destroy_node()
        self.harness_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

        if self._spin_error is not None:
            self.fail(f"Spin thread raised unexpected exception: {self._spin_error}")

    def _spin_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                self.executor.spin_once(timeout_sec=0.01)
        except Exception as exc:
            self._spin_error = exc

    def _wait_until(
        self,
        predicate: Callable[[Optional[Twist], Optional[Dict[str, Any]], int, int], bool],
        timeout_s: float,
        description: str,
    ) -> Tuple[Optional[Twist], Optional[Dict[str, Any]], int, int]:
        deadline = time.monotonic() + timeout_s
        last_snapshot: Tuple[Optional[Twist], Optional[Dict[str, Any]], int, int] = (None, None, 0, 0)

        while True:
            if self._spin_error is not None:
                self.fail(f"Spin thread exception: {self._spin_error}")

            last_snapshot = self.harness_node.get_snapshot()
            if predicate(*last_snapshot):
                return last_snapshot

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.fail(f"Timeout waiting for {description} within {timeout_s:.1f}s. Last: {last_snapshot}")

            time.sleep(min(0.02, remaining))

    def _bring_gate_to_run(self, clear_ranges: List[float]) -> None:
        """Helper driving startup dwell and single operator reset into RUN mode."""
        # 1. Provide steady nominal proposals and clear scan until dwell completes
        def _is_awaiting_reset(_twist: Optional[Twist], state: Optional[Dict[str, Any]], _b: int, _d: int) -> bool:
            self.harness_node.publish_nav_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return state is not None and state.get("mode") == "AWAITING_RESET"

        self._wait_until(_is_awaiting_reset, 5.0, "Gate startup dwell to reach AWAITING_RESET")

        # 2. Publish single operator reset request (pure action, outside predicate loop)
        self.harness_node.publish_reset("operator")

        # 3. Wait for RUN transition under continuous proposal feed
        def _is_running(_twist: Optional[Twist], state: Optional[Dict[str, Any]], _b: int, _d: int) -> bool:
            self.harness_node.publish_nav_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return state is not None and state.get("mode") == "RUN"

        self._wait_until(_is_running, 3.0, "Gate operator reset transition into RUN")

    def test_01_nav2_forward_cruise_and_active_topic_isolation(self) -> None:
        """
        Verifies:
        1. Forward linear cruise proposals pass through to /base/cmd_vel.
        2. Actively publishing to unmapped /cmd_vel does not leak to /base/cmd_vel
           or satisfy the gate's proposal feed.
        3. Default /cmd_vel_safe receives zero messages.
        """
        clear_ranges = [3.0] * DEFAULT_LIDAR_N_EXPECTED
        self._bring_gate_to_run(clear_ranges)
        self.harness_node.reset_telemetry_history()

        # Part A: Verify nominal forward cruise passthrough
        def _is_cruising(twist: Optional[Twist], state: Optional[Dict[str, Any]], b_cnt: int, _d: int) -> bool:
            self.harness_node.publish_nav_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return (
                b_cnt > 0
                and state is not None
                and twist is not None
                and state.get("mode") == "RUN"
                and math.isclose(twist.linear.x, 0.20, abs_tol=1e-3)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-3)
            )

        self._wait_until(_is_cruising, 2.0, "Nav2 forward cruise passthrough on /base/cmd_vel")

        # Part B: Active Default-Topic Isolation Injection
        # Stop /cmd_vel_nav and inject distinct proposals (0.35 m/s) exclusively onto /cmd_vel
        self.harness_node.reset_telemetry_history()
        for _ in range(5):
            self.harness_node.publish_default_proposal(linear_x=0.35, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            time.sleep(0.032)

        twist, _state, _b_cnt, default_safe_cnt = self.harness_node.get_snapshot()

        # Canary checks:
        self.assertEqual(
            default_safe_cnt,
            0,
            "Isolation leak: default /cmd_vel_safe received messages under Pattern B remapping",
        )
        if twist is not None:
            self.assertFalse(
                math.isclose(twist.linear.x, 0.35, abs_tol=1e-2),
                "Isolation leak: unmapped /cmd_vel proposal leaked through to /base/cmd_vel!",
            )

    def test_02_nav2_coordinated_arc_passthrough(self) -> None:
        """Verifies coordinated turning arc proposals (v_x > 0, w_z > 0) pass through."""
        clear_ranges = [3.0] * DEFAULT_LIDAR_N_EXPECTED
        self._bring_gate_to_run(clear_ranges)
        self.harness_node.reset_telemetry_history()

        target_vx = 0.15
        target_wz = 0.10

        def _is_turning(twist: Optional[Twist], state: Optional[Dict[str, Any]], b_cnt: int, _d: int) -> bool:
            self.harness_node.publish_nav_proposal(linear_x=target_vx, angular_z=target_wz)
            self.harness_node.publish_scan(clear_ranges)
            return (
                b_cnt > 0
                and state is not None
                and twist is not None
                and state.get("mode") == "RUN"
                and math.isclose(twist.linear.x, target_vx, abs_tol=1e-3)
                and math.isclose(twist.angular.z, target_wz, abs_tol=1e-3)
            )

        self._wait_until(_is_turning, 2.0, "Nav2 coordinated arc passthrough on /base/cmd_vel")

    def test_03_nav2_dynamic_obstacle_interception_clamps_zero(self) -> None:
        """Verifies that an obstacle breach during Nav2 motion immediately clamps setpoint to 0.0."""
        clear_ranges = [3.0] * DEFAULT_LIDAR_N_EXPECTED
        hazard_ranges = [0.15] * DEFAULT_LIDAR_N_EXPECTED
        self._bring_gate_to_run(clear_ranges)
        self.harness_node.reset_telemetry_history()

        def _is_tripped_and_clamped(
            twist: Optional[Twist], state: Optional[Dict[str, Any]], b_cnt: int, _d: int
        ) -> bool:
            # Proposer continues requesting motion, but corridor is obstructed
            self.harness_node.publish_nav_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(hazard_ranges)
            return (
                b_cnt > 0
                and state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_OBSTACLE"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_tripped_and_clamped, 2.0, "TRIP_OBSTACLE fail-closed clamp to 0.0 m/s")

    def test_04_nav2_proposal_stream_interruption_watchdog_trips(self) -> None:
        """Verifies that cessation of velocity proposals while sensors remain active trips watchdog."""
        clear_ranges = [3.0] * DEFAULT_LIDAR_N_EXPECTED
        self._bring_gate_to_run(clear_ranges)
        self.harness_node.reset_telemetry_history()

        # Step A: Establish verified active cruise
        def _is_active(twist: Optional[Twist], state: Optional[Dict[str, Any]], b_cnt: int, _d: int) -> bool:
            self.harness_node.publish_nav_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return (
                b_cnt > 0
                and state is not None
                and state.get("mode") == "RUN"
                and twist is not None
                and twist.linear.x > 0.15
            )

        self._wait_until(_is_active, 2.0, "Active cruise before proposal stream interruption")

        # Step B: Silence velocity proposals while keeping sensor feed fresh
        self.harness_node.reset_telemetry_history()

        def _is_watchdog_tripped(
            twist: Optional[Twist], state: Optional[Dict[str, Any]], b_cnt: int, _d: int
        ) -> bool:
            self.harness_node.publish_scan(clear_ranges)
            return (
                b_cnt > 0
                and state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_PROPOSER_STALE"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_watchdog_tripped, 3.0, "TRIP_PROPOSER_STALE following stream interruption")


if __name__ == "__main__":
    unittest.main()
