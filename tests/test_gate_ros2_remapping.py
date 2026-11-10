# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Live ROS 2 topic remapping integration test for QERRA supervisory gate node (Pattern B).

Verifies that topic remappings cleanly intercept untrusted planner proposals
(e.g. /cmd_vel_nav) and publish verified setpoints to custom base controller topics
(e.g. /base/cmd_vel), while confirming default topics are isolated.
"""
from __future__ import annotations

import json
import math
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

    from ros2.qerra_gate_node import QerraGateNode

    ROS2_AVAILABLE = True
except ImportError:
    rclpy = None
    SingleThreadedExecutor = None
    Node = Any
    qos_profile_sensor_data = Any
    Twist = Any
    LaserScan = Any
    String = Any
    QerraGateNode = Any
    ROS2_AVAILABLE = False


if ROS2_AVAILABLE:

    class RemappedTrafficHarnessNode(Node):
        """Harness node driving custom remapped topics and monitoring isolation."""

        def __init__(self) -> None:
            super().__init__("remapped_traffic_harness_node")
            self._lock = threading.Lock()

            # Publishers targeting the remapped topics
            self.pub_nav = self.create_publisher(Twist, "/cmd_vel_nav", 10)
            self.pub_scan = self.create_publisher(LaserScan, "/front_lidar/scan", qos_profile_sensor_data)
            self.pub_reset = self.create_publisher(String, "/gate/reset", 10)

            # Publisher targeting default /cmd_vel to test isolation
            self.pub_default_cmd = self.create_publisher(Twist, "/cmd_vel", 10)

            # Subscribers listening to custom base controller topic and default topic
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

        def _default_safe_cb(self, msg: Twist) -> None:
            with self._lock:
                self.default_safe_count += 1

        def _state_cb(self, msg: String) -> None:
            with self._lock:
                try:
                    self.latest_state_json = json.loads(msg.data)
                except Exception:
                    self.latest_state_json = None

        def get_telemetry_snapshot(self) -> Tuple[Optional[Twist], Optional[Dict[str, Any]]]:
            with self._lock:
                return self.latest_base_twist, self.latest_state_json

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

        def publish_scan(self, ranges: List[float], n_expected: int = 682) -> None:
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
class TestGateRos2Remapping(unittest.TestCase):
    """Verifies Pattern B topic remapping and isolation."""

    def setUp(self) -> None:
        # Initialize rclpy with node-specific remappings matching Pattern B topology
        rclpy.init(args=[
            "--ros-args",
            "-r", "qerra_gate_node:/cmd_vel:=/cmd_vel_nav",
            "-r", "qerra_gate_node:/cmd_vel_safe:=/base/cmd_vel",
            "-r", "qerra_gate_node:/scan:=/front_lidar/scan",
            "-p", "hsr_required:=false",
            "-p", "hsr_source:=none",
            "-p", "flight_log_path:=none",
        ])

        self.gate_node = QerraGateNode()
        self.harness_node = RemappedTrafficHarnessNode()

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

        self.executor.shutdown()
        self.gate_node.destroy_node()
        self.harness_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    def _spin_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                self.executor.spin_once(timeout_sec=0.01)
        except Exception as exc:
            self._spin_error = exc

    def _wait_until(
        self,
        predicate: Callable[[Optional[Twist], Optional[Dict[str, Any]]], bool],
        timeout_s: float,
        description: str,
    ) -> Tuple[Optional[Twist], Optional[Dict[str, Any]]]:
        deadline = time.monotonic() + timeout_s
        last_snapshot: Tuple[Optional[Twist], Optional[Dict[str, Any]]] = (None, None)

        while True:
            if self._spin_error is not None:
                self.fail(f"Spin thread exception: {self._spin_error}")

            last_snapshot = self.harness_node.get_telemetry_snapshot()
            if predicate(*last_snapshot):
                return last_snapshot

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.fail(f"Timeout waiting for {description} within {timeout_s:.1f}s. Last: {last_snapshot}")

            time.sleep(min(0.02, remaining))

    def test_remapped_topic_interception_and_isolation(self) -> None:
        """
        Verifies:
        1. Node receives proposals from remapped /cmd_vel_nav and outputs to /base/cmd_vel.
        2. Clamps velocity fail-closed on /base/cmd_vel on obstacle breach.
        3. Publishing to default /cmd_vel does not satisfy proposer freshness.
        """
        clear_ranges = [3.0] * 682
        hazard_ranges = [0.15] * 682

        # 1. Drive clear dwell to AWAITING_RESET using remapped topics
        def _is_awaiting_reset(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_nav_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return state is not None and state.get("mode") == "AWAITING_RESET"

        self._wait_until(_is_awaiting_reset, 5.0, "Gate to reach AWAITING_RESET on remapped topics")

        # 2. Reset into RUN mode
        def _is_running(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_nav_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_reset("operator")
            return state is not None and state.get("mode") == "RUN"

        self._wait_until(_is_running, 3.0, "Gate to enter RUN on remapped topics")

        # 3. Verify cruise setpoints appear on /base/cmd_vel (not /cmd_vel_safe)
        def _is_cruising_on_base(twist: Optional[Twist], _state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_nav_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return twist is not None and twist.linear.x > 0.15

        self._wait_until(_is_cruising_on_base, 2.0, "forward cruise output on /base/cmd_vel")
        self.assertEqual(
            self.harness_node.default_safe_count,
            0,
            "Default /cmd_vel_safe topic received messages despite being remapped to /base/cmd_vel!",
        )

        # 4. Verify obstacle breach clamps /base/cmd_vel to 0.0 m/s
        def _is_obstacle_tripped(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_nav_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(hazard_ranges)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_OBSTACLE"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_obstacle_tripped, 3.0, "TRIP_OBSTACLE clamp on /base/cmd_vel")

        # 5. Isolation Check: Silence /cmd_vel_nav, but publish to default /cmd_vel.
        # The node must NOT accept default /cmd_vel; it must trip TRIP_PROPOSER_STALE.
        def _is_proposer_stale(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_default_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return (
                state is not None
                and twist is not None
                and state.get("reason") == "TRIP_PROPOSER_STALE"
            )

        self._wait_until(
            _is_proposer_stale,
            3.0,
            "TRIP_PROPOSER_STALE confirming default /cmd_vel is ignored by remapped node",
        )


if __name__ == "__main__":
    unittest.main()
