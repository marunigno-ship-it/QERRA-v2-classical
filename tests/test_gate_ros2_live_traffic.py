# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Live ROS 2 pub/sub topic traffic integration tests for QERRA supervisory gate node.

Executes native multi-node DDS communication inside ROS 2 Jazzy container.
Skips cleanly without error on hosts lacking rclpy (e.g. Windows development host).
"""
from __future__ import annotations

import json
import math
import threading
import time
import unittest
from typing import Any, Dict, List, Optional, Tuple

try:
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import String

    from ros2.qerra_gate_node import QerraGateNode

    ROS2_AVAILABLE = True
except ImportError:
    rclpy = None
    SingleThreadedExecutor = None
    Node = Any
    Twist = Any
    LaserScan = Any
    String = Any
    QerraGateNode = Any
    ROS2_AVAILABLE = False


if ROS2_AVAILABLE:

    class TrafficHarnessNode(Node):
        """Active harness node for driving inputs and capturing live telemetry."""

        def __init__(self) -> None:
            super().__init__("traffic_harness_node")
            self._lock = threading.Lock()

            # Publishers
            self.pub_cmd = self.create_publisher(Twist, "/cmd_vel", 10)
            self.pub_scan = self.create_publisher(LaserScan, "/scan", 10)
            self.pub_reset = self.create_publisher(String, "/gate/reset", 10)

            # Telemetry subscribers
            self.sub_cmd_safe = self.create_subscription(
                Twist, "/cmd_vel_safe", self._cmd_safe_cb, 10
            )
            self.sub_state = self.create_subscription(
                String, "/gate/state", self._state_cb, 10
            )

            self.latest_safe_twist: Optional[Twist] = None
            self.latest_state_raw: Optional[str] = None
            self.latest_state_json: Optional[Dict[str, Any]] = None
            self.safe_twist_count = 0
            self.state_count = 0

        def _cmd_safe_cb(self, msg: Twist) -> None:
            with self._lock:
                self.latest_safe_twist = msg
                self.safe_twist_count += 1

        def _state_cb(self, msg: String) -> None:
            with self._lock:
                self.latest_state_raw = msg.data
                self.state_count += 1
                try:
                    self.latest_state_json = json.loads(msg.data)
                except Exception:
                    self.latest_state_json = None

        def get_telemetry_snapshot(self) -> Tuple[Optional[Twist], Optional[Dict[str, Any]]]:
            with self._lock:
                return self.latest_safe_twist, self.latest_state_json

        def publish_proposal(self, linear_x: float, angular_z: float) -> None:
            msg = Twist()
            msg.linear.x = float(linear_x)
            msg.angular.z = float(angular_z)
            self.pub_cmd.publish(msg)

        def publish_scan(self, ranges: List[float], n_expected: int = 682) -> None:
            if len(ranges) != n_expected:
                raise ValueError(f"Expected {n_expected} ranges, got {len(ranges)}")
            scan = LaserScan()
            scan.header.stamp = self.get_clock().now().to_msg()
            scan.header.frame_id = "base_laser_link"
            scan.angle_min = -2.0943951  # -120 deg
            scan.angle_max = 2.0943951   # +120 deg
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
class TestGateRos2LiveTopicTraffic(unittest.TestCase):
    """
    Live pub/sub topic traffic integration test verifying real DDS communication,
    startup dwell, operator reset, clear-corridor cruise, and obstacle clamping.
    """

    def setUp(self) -> None:
        # Initialize rclpy with explicit Layer 1A configuration (HSR disabled for pure topic test)
        rclpy.init(args=[
            "--ros-args",
            "-p", "hsr_required:=false",
            "-p", "hsr_source:=none",
            "-p", "flight_log_path:=none",
        ])

        self.gate_node = QerraGateNode()
        self.harness_node = TrafficHarnessNode()

        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.gate_node)
        self.executor.add_node(self.harness_node)

        self._stop_event = threading.Event()
        self._spin_thread = threading.Thread(target=self._spin_loop, daemon=True)
        self._spin_thread.start()

    def tearDown(self) -> None:
        self._stop_event.set()
        if self._spin_thread.is_alive():
            self._spin_thread.join(timeout=2.0)

        self.executor.shutdown()
        self.gate_node.destroy_node()
        self.harness_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    def _spin_loop(self) -> None:
        while not self._stop_event.is_set():
            self.executor.spin_once(timeout_sec=0.01)

    def test_live_topic_traffic_lifecycle_and_obstacle_trip(self) -> None:
        """
        Executes end-to-end pub/sub verification:
        1. Emits continuous clear corridor scans and proposals to satisfy 1.0s dwell.
        2. Asserts transition to AWAITING_RESET.
        3. Emits operator reset string and asserts transition to RUN.
        4. Verifies non-zero proposal passthrough on /cmd_vel_safe.
        5. Injects obstacle breaching stopping distance and verifies fail-closed 0.0 m/s clamp.
        """
        clear_ranges = [3.0] * 682      # 3.0m clear corridor across all 682 beams
        hazard_ranges = [0.15] * 682    # 150mm obstacle (< 360mm stopping envelope)

        # --------------------------------------------------------------------
        # Phase 1: Clear Corridor Startup Dwell (Must reach AWAITING_RESET)
        # --------------------------------------------------------------------
        t_start = time.monotonic()
        awaiting_reset_reached = False
        last_state = None

        while time.monotonic() - t_start < 5.0:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            time.sleep(0.02)  # ~50 Hz stream rate

            _, state = self.harness_node.get_telemetry_snapshot()
            if state is not None:
                last_state = state
                if state.get("mode") == "AWAITING_RESET":
                    awaiting_reset_reached = True
                    break

        self.assertTrue(
            awaiting_reset_reached,
            f"Gate failed to reach AWAITING_RESET within 5.0s. Last state: {last_state}",
        )

        # --------------------------------------------------------------------
        # Phase 2: Operator Reset to Enter Mode.RUN
        # --------------------------------------------------------------------
        t_reset = time.monotonic()
        run_mode_reached = False

        while time.monotonic() - t_reset < 3.0:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_reset("operator")
            time.sleep(0.02)

            _, state = self.harness_node.get_telemetry_snapshot()
            if state is not None:
                last_state = state
                if state.get("mode") == "RUN":
                    run_mode_reached = True
                    break

        self.assertTrue(
            run_mode_reached,
            f"Gate failed to enter Mode.RUN after operator reset. Last state: {last_state}",
        )

        # --------------------------------------------------------------------
        # Phase 3: Verify Clear-Corridor Cruise on /cmd_vel_safe
        # --------------------------------------------------------------------
        t_cruise = time.monotonic()
        cruise_command_verified = False
        last_safe_twist = None

        while time.monotonic() - t_cruise < 2.0:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            time.sleep(0.02)

            safe_twist, state = self.harness_node.get_telemetry_snapshot()
            if safe_twist is not None:
                last_safe_twist = safe_twist
                # At 0.20 m/s linear proposal, linear.x must reflect forward motion (> 0.15 m/s)
                if safe_twist.linear.x > 0.15 and math.isclose(safe_twist.angular.z, 0.0, abs_tol=1e-3):
                    cruise_command_verified = True
                    break

        self.assertTrue(
            cruise_command_verified,
            f"Gate did not output forward safe twist in Mode.RUN. Last twist: {last_safe_twist}",
        )

        # --------------------------------------------------------------------
        # Phase 4: Inject Obstacle Hazard and Verify Immediate Clamping to 0.0
        # --------------------------------------------------------------------
        t_hazard = time.monotonic()
        obstacle_trip_verified = False

        while time.monotonic() - t_hazard < 3.0:
            # Continue proposing forward velocity, but inject breach on /scan
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(hazard_ranges)
            time.sleep(0.02)

            safe_twist, state = self.harness_node.get_telemetry_snapshot()
            if state is not None and safe_twist is not None:
                if (
                    state.get("mode") == "TRIPPED"
                    and state.get("reason") == "TRIP_OBSTACLE"
                    and math.isclose(safe_twist.linear.x, 0.0, abs_tol=1e-6)
                    and math.isclose(safe_twist.angular.z, 0.0, abs_tol=1e-6)
                ):
                    obstacle_trip_verified = True
                    break

        self.assertTrue(
            obstacle_trip_verified,
            f"Gate failed to clamp fail-closed on obstacle breach. Last state: {state}, Twist: {safe_twist}",
        )


if __name__ == "__main__":
    unittest.main()
