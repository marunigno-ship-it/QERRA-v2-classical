# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Live dual-protocol integration tests for QERRA supervisory gate node.

Executes concurrent ROS 2 DDS topic traffic and Layer 1B UDP reflex telemetry
inside the official ROS 2 Jazzy container.
Skips cleanly without error on hosts lacking rclpy (e.g. Windows development host).
"""
from __future__ import annotations

import json
import math
import socket
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

    class DualProtocolHarnessNode(Node):
        """Harness node driving DDS topics and UDP reflex datagrams concurrently."""

        def __init__(self, udp_port: int = 5008) -> None:
            super().__init__("dual_protocol_harness_node")
            self._lock = threading.Lock()
            self._udp_port = udp_port

            # UDP reflex sender
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp_sock.setblocking(False)

            # Publishers
            self.pub_cmd = self.create_publisher(Twist, "/cmd_vel", 10)
            self.pub_scan = self.create_publisher(LaserScan, "/scan", qos_profile_sensor_data)
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

        def _cmd_safe_cb(self, msg: Twist) -> None:
            with self._lock:
                self.latest_safe_twist = msg

        def _state_cb(self, msg: String) -> None:
            with self._lock:
                self.latest_state_raw = msg.data
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

        def send_hsr_packet(
            self,
            obs_id: int,
            state: str = "CLEAR",
            distress_permille: int = 0,
        ) -> None:
            """Transmits a causal HSR reflex datagram stamped to current ROS clock."""
            now_us = self.get_clock().now().nanoseconds // 1_000
            payload = json.dumps({
                "obs_id": int(obs_id),
                "t_obs_us": now_us,
                "t_emit_us": now_us + 1_000,
                "distress_permille": int(distress_permille),
                "state": str(state),
            }).encode("utf-8")
            self._udp_sock.sendto(payload, ("127.0.0.1", self._udp_port))

        def close(self) -> None:
            try:
                self._udp_sock.close()
            except OSError:
                pass


@unittest.skipUnless(ROS2_AVAILABLE, "Requires native ROS 2 (rclpy) installation")
class TestGateRos2DualProtocol(unittest.TestCase):
    """
    Live co-execution tests verifying concurrent ROS 2 DDS pub/sub and Layer 1B UDP telemetry:
    1. Dual-dwell recovery (Lidar clear + HSR clear dwell) and acute distress reflex stop.
    2. Stale HSR heartbeat fail-closed watchdog trip (96 ms ceiling).
    """

    HSR_PORT = 5008

    def setUp(self) -> None:
        # Enable UDP HSR reflex input and fail-closed requirement
        rclpy.init(args=[
            "--ros-args",
            "-p", "hsr_required:=true",
            "-p", "hsr_source:=udp",
            "-p", f"hsr_port:={self.HSR_PORT}",
            "-p", "flight_log_path:=none",
        ])

        self.gate_node = QerraGateNode()
        self.harness_node = DualProtocolHarnessNode(udp_port=self.HSR_PORT)

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
        self.harness_node.close()
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
        """Bounded polling helper with explicit monotonic deadline and exception propagation."""
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

    def _drive_to_run_dual_protocol(self, clear_ranges: List[float]) -> int:
        """
        Drives the gate into Mode.RUN under active dual-protocol inputs.
        Returns the highest obs_id emitted.
        """
        obs_counter = [0]

        # 1. Drive clear dwell until AWAITING_RESET
        def _is_awaiting_reset(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            obs_counter[0] += 1
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.send_hsr_packet(obs_id=obs_counter[0], state="CLEAR", distress_permille=0)
            return state is not None and state.get("mode") == "AWAITING_RESET"

        self._wait_until(_is_awaiting_reset, 6.0, "Gate to reach AWAITING_RESET under dual-protocol dwell")

        # 2. Emit operator reset until Mode.RUN is reached
        def _is_running(_twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            obs_counter[0] += 1
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.send_hsr_packet(obs_id=obs_counter[0], state="CLEAR", distress_permille=0)
            self.harness_node.publish_reset("operator")
            return state is not None and state.get("mode") == "RUN"

        self._wait_until(_is_running, 3.0, "Gate to enter Mode.RUN after operator reset")
        return obs_counter[0]

    def test_dual_protocol_clear_dwell_and_acute_distress_trip(self) -> None:
        """
        Verifies that concurrent DDS cruise is overridden fail-closed by an acute
        distress UDP packet on port 5008 (TRIP_HSR_CRITICAL / 0.0 m/s clamp).
        """
        clear_ranges = [3.0] * 682

        # 1. Bring gate to Mode.RUN with advancing CLEAR UDP packets
        obs_id = self._drive_to_run_dual_protocol(clear_ranges)

        # 2. Verify steady cruise while both channels are CLEAR
        obs_holder = [obs_id]

        def _is_cruising(twist: Optional[Twist], _state: Optional[Dict[str, Any]]) -> bool:
            obs_holder[0] += 1
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            self.harness_node.send_hsr_packet(obs_id=obs_holder[0], state="CLEAR", distress_permille=0)
            return twist is not None and twist.linear.x > 0.15 and math.isclose(twist.angular.z, 0.0, abs_tol=1e-3)

        self._wait_until(_is_cruising, 2.0, "steady cruise on /cmd_vel_safe under dual protocol")

        # 3. Transmit CRITICAL distress reflex packet over UDP while DDS remains healthy
        def _is_distress_tripped(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            obs_holder[0] += 1
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            # Acute physical distress injected via UDP
            self.harness_node.send_hsr_packet(obs_id=obs_holder[0], state="CRITICAL", distress_permille=850)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_HSR_CRITICAL"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_distress_tripped, 3.0, "TRIP_HSR_CRITICAL fail-closed clamp on acute UDP distress")

    def test_dual_protocol_stale_heartbeat_trip(self) -> None:
        """
        Verifies that when hsr_required=True, cutting the UDP telemetry stream
        triggers the 96 ms HSR staleness watchdog (TRIP_HSR_STALE) and forces
        /cmd_vel_safe to 0.0 m/s fail-closed while DDS topics remain active.
        """
        clear_ranges = [3.0] * 682

        # 1. Bring gate to Mode.RUN with advancing CLEAR UDP packets
        self._drive_to_run_dual_protocol(clear_ranges)

        # 2. Stop publishing UDP packets completely; continue publishing DDS proposals and scans
        def _is_hsr_stale(twist: Optional[Twist], state: Optional[Dict[str, Any]]) -> bool:
            # ONLY publish DDS traffic; zero UDP datagrams emitted
            self.harness_node.publish_proposal(linear_x=0.20, angular_z=0.0)
            self.harness_node.publish_scan(clear_ranges)
            return (
                state is not None
                and twist is not None
                and state.get("mode") == "TRIPPED"
                and state.get("reason") == "TRIP_HSR_STALE"
                and math.isclose(twist.linear.x, 0.0, abs_tol=1e-6)
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-6)
            )

        self._wait_until(_is_hsr_stale, 3.0, "TRIP_HSR_STALE watchdog clamp on UDP telemetry loss")


if __name__ == "__main__":
    unittest.main()
