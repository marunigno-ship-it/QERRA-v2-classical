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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
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
    Odometry = Any
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

            # Publishers: explicit sensor-data profile (Best Effort) for scan interoperability
            self.pub_cmd = self.create_publisher(Twist, "/cmd_vel", 10)
            self.pub_scan = self.create_publisher(LaserScan, "/scan", qos_profile_sensor_data)
            self.pub_reset = self.create_publisher(String, "/gate/reset", 10)
            self.pub_odom = self.create_publisher(Odometry, "/odom", 10)
            self.pub_hsr = self.create_publisher(String, "/hsr/telemetry", 10)

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
            self.seen_events: Set[str] = set()
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
                    parsed = json.loads(msg.data)
                    self.latest_state_json = parsed
                    for ev in parsed.get("events", []):
                        self.seen_events.add(ev)
                except Exception:
                    self.latest_state_json = None

        def clear_seen_events(self) -> None:
            with self._lock:
                self.seen_events.clear()

        def has_seen_event(self, event_name: str) -> bool:
            with self._lock:
                return event_name in self.seen_events

        def get_telemetry_snapshot(self) -> Tuple[Optional[Twist], Optional[Dict[str, Any]]]:
            with self._lock:
                return self.latest_safe_twist, self.latest_state_json

        def publish_proposal(self, linear_x: float, angular_z: float) -> None:
            msg = Twist()
            msg.linear.x = float(linear_x)
            msg.angular.z = float(angular_z)
            self.pub_cmd.publish(msg)

        def publish_odom(self, linear_x: float, angular_z: float) -> None:
            odom = Odometry()
            odom.header.stamp = self.get_clock().now().to_msg()
            odom.header.frame_id = "odom"
            odom.child_frame_id = "base_footprint"
            odom.twist.twist.linear.x = float(linear_x)
            odom.twist.twist.angular.z = float(angular_z)
            self.pub_odom.publish(odom)

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

        def publish_hsr(self, payload: str) -> None:
            msg = String()
            msg.data = payload
            self.pub_hsr.publish(msg)


@unittest.skipUnless(ROS2_AVAILABLE, "Requires native ROS 2 (rclpy) installation")
class TestGateRos2LiveTopicTraffic(unittest.TestCase):
    """
    Live pub/sub topic traffic integration tests verifying DDS communication:
    1. Lifecycle, dwell, operator reset, cruise passthrough, and obstacle clamping.
    2. Negative Path A: Sensor loss watchdog (96 ms staleness ceiling).
    3. Negative Path C: Active hazard reset refusal (RESET_REJECTED_HAZARD event).
    4. Negative Path B: Proposer timeout watchdog (150 ms freshness ceiling).
    5. Phase 1: Non-finite Twist command inhibition, recovery, and watchdog escalation.
    6. Live DDS /odom pub/sub ingestion, translation, freshness watchdog, and fail-closed NaN rejection.
    """

    def setUp(self) -> None:
        # Initialize rclpy with explicit Layer 1A configuration (HSR disabled for pure topic tests)
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
        """
        Bounded polling helper with explicit monotonic deadline and exception propagation.
        Guarantees deterministic failure reporting without silent hangs.
        """
        deadline = time.monotonic() + timeout_s
        last_snapshot: Tuple[Optional[Twist], Optional[Dict[str, Any]]] = (None, None)

        while True:
            if self._spin_error is not None:
                self.fail(f"Background spin thread died with exception: {self._spin_error}")

            last_snapshot = self.harness_node.get_telemetry_snapshot()
            if predicate(*last_snapshot):
                return last_snapshot

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.fail(
                    f"Timeout waiting for {description} within {timeout_s:.1f}s. "
                    f"Last snapshot: {last_snapshot}"
                )

            time.sleep(min(0.02, remaining))

    def _drive_to_run(self, clear_ranges: List[float]) -> None:
        """Helper driving the gate from initial latch through 1.0s dwell into Mode.RUN."""
        def _is_awaiting_reset(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return state is not None and state.get("mode") == "AWAITING_RESET"

        self._wait_until(_is_awaiting_reset, 5.0, "Gate to reach AWAITING_RESET during clear dwell")

        def _is_running(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_reset("operator")
            return state is not None and state.get("mode") == "RUN"

        self._wait_until(_is_running, 3.0, "Gate to enter Mode.RUN after operator reset")

    def test_live_topic_traffic_lifecycle_and_obstacle_trip(self) -> None:
        """Verifies clear-corridor cruise followed by immediate fail-closed obstacle stop."""
        clear_ranges = [3.0] * 682
        hazard_ranges = [0.15] * 682

        self._drive_to_run(clear_ranges)

        def _is_cruising(twist: Optional[Twist], _state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return twist is not None and twist.linear.x > 0.15 and math.isclose(twist.angular.z, 0.0, abs_tol=1e-3)

        self._wait_until(_is_cruising, 2.0, "forward cruise output on /cmd_vel_safe")

        def _is_obstacle_tripped(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(hazard_ranges)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_OBSTACLE"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_obstacle_tripped, 3.0, "TRIP_OBSTACLE fail-closed clamp on obstacle breach")

    def test_live_topic_traffic_sensor_loss_watchdog(self) -> None:
        """
        Verifies Negative Path A: cutting the /scan topic feed while in Mode.RUN
        triggers the 96 ms sensor staleness watchdog (TRIP_SENSOR_INVALID)
        and forces /cmd_vel_safe to 0.0 m/s fail-closed.
        """
        clear_ranges = [3.0] * 682
        self._drive_to_run(clear_ranges)

        def _is_sensor_invalid(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_SENSOR_INVALID"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_sensor_invalid, 3.0, "TRIP_SENSOR_INVALID watchdog clamp on scan loss")

    def test_live_topic_traffic_reset_rejected_under_active_obstacle(self) -> None:
        """
        Verifies Negative Path C: an operator reset cannot override an active physical hazard.
        """
        clear_ranges = [3.0] * 682
        hazard_ranges = [0.15] * 682

        self._drive_to_run(clear_ranges)

        def _is_tripped_on_obstacle(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(hazard_ranges)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_OBSTACLE"
            )

        self._wait_until(_is_tripped_on_obstacle, 3.0, "Gate to trip on obstacle breach")

        def _is_reset_rejected(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(hazard_ranges)
            self.harness_node.publish_reset("operator")
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_OBSTACLE"
                and "RESET_REJECTED_HAZARD" in state.get("events", [])
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_reset_rejected, 3.0, "RESET_REJECTED_HAZARD event while obstacle persists")

    def test_live_topic_traffic_proposer_timeout_watchdog(self) -> None:
        """
        Verifies Negative Path B: cutting /cmd_vel triggers proposal freshness watchdog (150 ms).
        """
        clear_ranges = [3.0] * 682
        self._drive_to_run(clear_ranges)

        def _is_proposer_stale(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_scan(clear_ranges)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_PROPOSER_STALE"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_proposer_stale, 3.0, "TRIP_PROPOSER_STALE watchdog clamp on /cmd_vel silence")

    def test_live_topic_traffic_non_finite_twist_inhibition_and_recovery(self) -> None:
        """Phase 1: Verifies live DDS handling of non-finite Twist proposals."""
        clear_ranges = [3.0] * 682
        self._drive_to_run(clear_ranges)

        def _is_cruising(twist: Optional[Twist], _state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return twist is not None and twist.linear.x > 0.15

        self._wait_until(_is_cruising, 2.0, "active cruise before NaN injection")

        self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
        self.harness_node.publish_scan(clear_ranges)
        time.sleep(0.035)

        self.harness_node.clear_seen_events()
        self.harness_node.publish_proposal(linear_x=float("nan"), angular_z=0.0)

        def _is_inhibited(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_scan(clear_ranges)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "RUN"
                and self.harness_node.has_seen_event("MSG_REJECTED_INVALID")
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_inhibited, 1.0, "immediate command inhibition on NaN Twist")

        def _is_recovered(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "RUN"
                and twist.linear.x > 0.15
            )

        self._wait_until(_is_recovered, 2.0, "automatic cruise recovery after NaN clears")

        def _is_escalated_stale(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=float("-inf"), angular_z=float("inf"))
            self.harness_node.publish_scan(clear_ranges)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_PROPOSER_STALE"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(
            _is_escalated_stale,
            3.0,
            "TRIP_PROPOSER_STALE watchdog escalation under continuous Inf Twist stream",
        )

    def test_live_topic_traffic_odom_pub_sub_and_watchdog(self) -> None:
        """Verifies live DDS pub/sub topic traffic for /odom."""
        clear_ranges = [3.0] * 682
        self._drive_to_run(clear_ranges)

        def _is_odom_forward(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_odom(linear_x=0.20, angular_z=0.0)
            return (
                state is not None
                and state.get("mode") == "RUN"
                and state.get("meas_left_urad_s") == 2_040_816
                and state.get("meas_right_urad_s") == 2_040_816
            )

        self._wait_until(_is_odom_forward, 3.0, "live /odom forward twist reflection in telemetry")

        def _is_odom_turning(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_odom(linear_x=0.0, angular_z=1.0)
            return (
                state is not None
                and state.get("mode") == "RUN"
                and state.get("meas_left_urad_s") == -2_063_265
                and state.get("meas_right_urad_s") == 2_063_265
            )

        self._wait_until(_is_odom_turning, 3.0, "live /odom in-place spin reflection in telemetry")

        def _is_odom_stale(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return (
                state is not None
                and state.get("mode") == "RUN"
                and state.get("meas_left_urad_s") is None
                and state.get("meas_right_urad_s") is None
            )

        self._wait_until(_is_odom_stale, 3.0, "live /odom 100 ms staleness watchdog drop to null")

        self.harness_node.publish_odom(linear_x=0.20, angular_z=0.0)
        self._wait_until(_is_odom_forward, 2.0, "re-establishing fresh odometry before NaN injection")

        def _is_odom_nan_dropped(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_odom(linear_x=float("nan"), angular_z=0.0)
            return (
                state is not None
                and state.get("mode") == "RUN"
                and state.get("meas_left_urad_s") is None
                and state.get("meas_right_urad_s") is None
            )

        self._wait_until(_is_odom_nan_dropped, 2.0, "live /odom NaN fail-closed drop to null")


@unittest.skipUnless(ROS2_AVAILABLE, "Requires native ROS 2 (rclpy) installation")
class TestGateRos2LiveHsrTopicTraffic(unittest.TestCase):
    """
    Live DDS pub/sub integration tests for ROS-native /hsr/telemetry (hsr_source:='topic'):
    1. Continuous fresh CLEAR frames allow 1.0s dwell to AWAITING_RESET and operator reset into RUN.
    2. Acute distress (CRITICAL) JSON payload trips gate to TRIP_HSR_CRITICAL and clamps to (0.0, 0.0).
    3. Frozen frame detection (repeated obs_id) trips gate to TRIP_HSR_INVALID and sets hsr_frozen: true.
    4. Cutting the /hsr/telemetry topic feed trips 96ms staleness watchdog (TRIP_HSR_STALE).
    """

    def setUp(self) -> None:
        rclpy.init(args=[
            "--ros-args",
            "-p", "hsr_required:=true",
            "-p", "hsr_source:=topic",
            "-p", "hsr_topic:=/hsr/telemetry",
            "-p", "flight_log_path:=none",
        ])

        self.gate_node = QerraGateNode()
        self.harness_node = TrafficHarnessNode()

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
                self.fail(f"Background spin thread died with exception: {self._spin_error}")

            last_snapshot = self.harness_node.get_telemetry_snapshot()
            if predicate(*last_snapshot):
                return last_snapshot

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.fail(
                    f"Timeout waiting for {description} within {timeout_s:.1f}s. "
                    f"Last snapshot: {last_snapshot}"
                )

            time.sleep(min(0.02, remaining))

    def test_live_hsr_topic_lifecycle_distress_freeze_and_watchdog(self) -> None:
        """Verifies complete Layer 1B ROS-native topic integration over live DDS."""
        clear_ranges = [3.0] * 682
        obs_id = 0

        # Helper to construct fresh valid HSR telemetry JSON payload
        def _make_hsr_json(obs: int, state: str = "CLEAR", permille: int = 0) -> str:
            now_us = self.harness_node.get_clock().now().nanoseconds // 1000
            t_obs = max(0, now_us - 10_000)  # 10 ms past to ensure t_rx_us >= t_obs_us
            return json.dumps({
                "obs_id": obs,
                "t_obs_us": t_obs,
                "t_emit_us": t_obs + 1_000,
                "distress_permille": permille,
                "state": state,
                "hazard_proximity": False,
                "persons_nearby_count": 2,
            })

        # 1. Drive clear dwell to AWAITING_RESET via live DDS topic /hsr/telemetry
        def _is_awaiting_reset(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            nonlocal obs_id
            obs_id += 1
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_hsr(_make_hsr_json(obs_id, state="CLEAR"))
            return state is not None and state.get("mode") == "AWAITING_RESET"

        self._wait_until(_is_awaiting_reset, 5.0, "Gate to reach AWAITING_RESET with live /hsr/telemetry topic")

        # 2. Reset into Mode.RUN
        def _is_running(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            nonlocal obs_id
            obs_id += 1
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_hsr(_make_hsr_json(obs_id, state="CLEAR"))
            self.harness_node.publish_reset("operator")
            return state is not None and state.get("mode") == "RUN"

        self._wait_until(_is_running, 3.0, "Gate to enter Mode.RUN on live topic HSR")

        # 3. Verify forward cruise output on /cmd_vel_safe
        def _is_cruising(twist: Optional[Twist], _state: Optional[Dict[str, Any]]) -> bool:
            nonlocal obs_id
            obs_id += 1
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_hsr(_make_hsr_json(obs_id, state="CLEAR"))
            return twist is not None and twist.linear.x > 0.15

        self._wait_until(_is_cruising, 2.0, "forward cruise with live /hsr/telemetry stream")

        # 4. Inject CRITICAL acute distress frame over /hsr/telemetry topic -> Trip Gate
        obs_id += 1
        crit_json = _make_hsr_json(obs_id, state="CRITICAL", permille=850)

        def _is_distress_tripped(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_hsr(crit_json)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_HSR_CRITICAL"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_distress_tripped, 3.0, "TRIP_HSR_CRITICAL trip on live /hsr/telemetry CRITICAL frame")

        # 5. Restore advancing CLEAR frames to clear acute distress, then inject frozen frame (duplicate obs_id)
        # Drive through dwell to reset
        def _is_reset_ready(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            nonlocal obs_id
            obs_id += 1
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_hsr(_make_hsr_json(obs_id, state="CLEAR"))
            return state is not None and state.get("mode") == "AWAITING_RESET"

        self._wait_until(_is_reset_ready, 5.0, "recovery to AWAITING_RESET")

        # Reset into RUN
        self._wait_until(_is_running, 3.0, "re-entering RUN")

        # Now send frozen frame (repeat same obs_id) -> must latch freeze and trip TRIP_HSR_INVALID
        frozen_json = _make_hsr_json(obs_id, state="CLEAR")

        def _is_frozen_tripped(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.publish_hsr(frozen_json)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_HSR_INVALID"
                and state.get("hsr_frozen") is True
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_frozen_tripped, 3.0, "TRIP_HSR_INVALID and hsr_frozen latch on duplicate obs_id")


if __name__ == "__main__":
    unittest.main()
