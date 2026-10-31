# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""QERRA ROS 2 supervisory gate node.

Provides standard ROS 2 node wrapping around the deterministic gate_core.py v0.4
engine, alongside pure-Python kinematic, lidar, and HSR reflex translators that
execute independently on hosts without ROS 2 installed.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from gate.gate_config import get_live_gate_params
from gate.gate_core import (
    GATE_CORE_VERSION,
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
from gate.gate_ipc import DEFAULT_HSR_PORT
from gate.gate_lidar import CorridorFilter, LidarPipeline
from gate.gate_link import DEFAULT_STATE_PORT, create_state_sender, send_state
from ros2.hsr_receiver import HsrReceiver

NODE_VERSION = "0.3.0"

# PAL Robotics TIAGo base physical dimensions & kinematics
DEFAULT_WHEEL_RADIUS_M: float = 0.098       # 98 mm radius
DEFAULT_TRACK_WIDTH_M: float = 0.4044       # 404.4 mm wheel separation
DEFAULT_ROBOT_HALF_WIDTH_M: float = 0.32    # 0.27m base half-width + 0.05m margin

# Hokuyo URG-04LX onboard lidar sensor defaults
DEFAULT_LIDAR_N_EXPECTED: int = 682         # 682 samples
DEFAULT_LIDAR_FOV_RAD: float = 4.1887902    # 240 degrees in radians

try:
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import String

    ROS2_AVAILABLE = True
    ROS2_IMPORT_ERROR = None
except ImportError as exc:
    rclpy = None
    Node = object  # Fallback base class for linting on non-ROS hosts
    Twist = None
    LaserScan = None
    String = None
    ROS2_AVAILABLE = False
    ROS2_IMPORT_ERROR = repr(exc)


# ----------------------------------------------------------------------------
# Pure Kinematic Translators (Zero ROS 2 Dependencies)
# ----------------------------------------------------------------------------
def twist_to_wheel_speeds(
    linear_x_mps: float,
    angular_z_radps: float,
    *,
    track_width_m: float = DEFAULT_TRACK_WIDTH_M,
    wheel_radius_m: float = DEFAULT_WHEEL_RADIUS_M,
) -> Tuple[int, int]:
    """
    Translates body linear/angular twist to integer left and right wheel speeds
    in micro-radians per second (urad/s). Fails closed on NaN/Inf.
    """
    if not math.isfinite(linear_x_mps) or not math.isfinite(angular_z_radps):
        raise ValueError(
            f"Velocities must be finite: linear={linear_x_mps!r}, angular={angular_z_radps!r}"
        )
    if track_width_m <= 0.0 or wheel_radius_m <= 0.0:
        raise ValueError("Kinematic dimensions must be strictly positive.")

    half_track = track_width_m / 2.0
    v_left = linear_x_mps - (angular_z_radps * half_track)
    v_right = linear_x_mps + (angular_z_radps * half_track)

    w_left_radps = v_left / wheel_radius_m
    w_right_radps = v_right / wheel_radius_m

    return int(round(w_left_radps * 1_000_000)), int(round(w_right_radps * 1_000_000))


def wheel_speeds_to_twist(
    cmd_left_urad_s: int,
    cmd_right_urad_s: int,
    *,
    track_width_m: float = DEFAULT_TRACK_WIDTH_M,
    wheel_radius_m: float = DEFAULT_WHEEL_RADIUS_M,
) -> Tuple[float, float]:
    """Translates integer gate wheel commands (urad/s) back into body twist (v_x, w_z)."""
    if track_width_m <= 0.0 or wheel_radius_m <= 0.0:
        raise ValueError("Kinematic dimensions must be strictly positive.")

    w_left_radps = cmd_left_urad_s / 1_000_000.0
    w_right_radps = cmd_right_urad_s / 1_000_000.0

    v_left = w_left_radps * wheel_radius_m
    v_right = w_right_radps * wheel_radius_m

    linear_x = (v_right + v_left) / 2.0
    angular_z = (v_right - v_left) / track_width_m

    return linear_x, angular_z


def twist_to_proposal(
    seq: int,
    sim_stamp_us: int,
    linear_x_mps: float,
    angular_z_radps: float,
    *,
    session_id: int = 0,
    track_width_m: float = DEFAULT_TRACK_WIDTH_M,
    wheel_radius_m: float = DEFAULT_WHEEL_RADIUS_M,
) -> Proposal:
    """Constructs a validated Proposal object from twist velocity inputs."""
    left_urad_s, right_urad_s = twist_to_wheel_speeds(
        linear_x_mps,
        angular_z_radps,
        track_width_m=track_width_m,
        wheel_radius_m=wheel_radius_m,
    )
    return Proposal(
        seq=seq,
        sim_stamp_us=sim_stamp_us,
        left_urad_s=left_urad_s,
        right_urad_s=right_urad_s,
        session_id=session_id,
    )


# ----------------------------------------------------------------------------
# Pure Lidar Translators (Zero ROS 2 Dependencies)
# ----------------------------------------------------------------------------
def create_lidar_pipeline(
    n_samples: int,
    fov_rad: float,
    *,
    half_width_m: float = DEFAULT_ROBOT_HALF_WIDTH_M,
) -> LidarPipeline:
    """Factory helper creating an authoritative LidarPipeline and CorridorFilter."""
    corridor = CorridorFilter(n_samples=n_samples, fov_rad=fov_rad, half_width_m=half_width_m)
    return LidarPipeline(corridor=corridor)


def process_laser_scan(
    ranges: Optional[Sequence[float]],
    stamp_sec: int,
    stamp_nanosec: int,
    pipeline: LidarPipeline,
    *,
    stalled: bool = False,
) -> Tuple[Optional[List[float]], Optional[int], int]:
    """Translates raw LaserScan ranges and ROS sec/nanosec timestamps into corridor returns."""
    if stamp_sec < 0 or stamp_nanosec < 0:
        raise ValueError("Timestamps must be non-negative.")
    if not isinstance(pipeline, LidarPipeline):
        raise TypeError("pipeline must be an instance of LidarPipeline")

    stamp_us = int(stamp_sec * 1_000_000 + stamp_nanosec // 1_000)
    return pipeline.process(ranges, stamp_us, stalled=stalled)


def format_gate_state_json(
    state: GateState,
    result_record: Dict[str, Any],
    *,
    hsr_source: str = "none",
    hsr_required: bool = False,
    hsr_drained: int = 0,
    hsr_error: Optional[str] = None,
) -> str:
    """Formats gate decision and state metrics into a clean JSON string."""
    payload = {
        "node_version": NODE_VERSION,
        "gate_version": GATE_CORE_VERSION,
        "mode": state.mode.value,
        "reason": result_record.get("reason"),
        "d_stop_mm": result_record.get("d_stop_mm"),
        "lidar_min_mm": result_record.get("lidar_min_mm"),
        "hsr_status": result_record.get("hsr_status"),
        "hsr_source": hsr_source,
        "hsr_required": hsr_required,
        "hsr_drained_total": hsr_drained,
        "hsr_socket_error": hsr_error,
        "proposal_seq": result_record.get("proposal_seq"),
        "proposal_age_us": result_record.get("proposal_age_us"),
        "cmd_left_urad_s": result_record.get("cmd_left_urad_s"),
        "cmd_right_urad_s": result_record.get("cmd_right_urad_s"),
    }
    return json.dumps(payload, separators=(",", ":"))


# ----------------------------------------------------------------------------
# ROS 2 Host Guard & Entry Point
# ----------------------------------------------------------------------------
def require_ros2() -> None:
    """Raise a clear error if rclpy could not be imported."""
    if not ROS2_AVAILABLE:
        raise RuntimeError(
            "rclpy is not importable in this environment; the QERRA gate "
            "node cannot run here. Import error: " + str(ROS2_IMPORT_ERROR)
        )


# ----------------------------------------------------------------------------
# ROS 2 Supervisory Gate Node Class (Active when ROS 2 is available)
# ----------------------------------------------------------------------------
if ROS2_AVAILABLE:

    class QerraGateNode(Node):
        """
        ROS 2 Simplex Supervisory Gate Node. Holds exclusive 32 ms write
        authority over /cmd_vel_safe to protect the robot base controller.
        """

        def __init__(self) -> None:
            super().__init__("qerra_gate_node")

            self.declare_parameter("rate_hz", 31.25)
            self.declare_parameter("track_width_m", DEFAULT_TRACK_WIDTH_M)
            self.declare_parameter("wheel_radius_m", DEFAULT_WHEEL_RADIUS_M)
            self.declare_parameter("robot_half_width_m", DEFAULT_ROBOT_HALF_WIDTH_M)
            self.declare_parameter("lidar_n_expected", DEFAULT_LIDAR_N_EXPECTED)
            self.declare_parameter("lidar_fov_rad", DEFAULT_LIDAR_FOV_RAD)
            self.declare_parameter("hsr_source", "udp")
            self.declare_parameter("hsr_port", DEFAULT_HSR_PORT)
            self.declare_parameter("hsr_required", True)
            self.declare_parameter("state_port", DEFAULT_STATE_PORT)

            self._track_width_m = float(self.get_parameter("track_width_m").value)
            self._wheel_radius_m = float(self.get_parameter("wheel_radius_m").value)
            self._half_width_m = float(self.get_parameter("robot_half_width_m").value)
            self._lidar_n_expected = int(self.get_parameter("lidar_n_expected").value)
            self._lidar_fov_rad = float(self.get_parameter("lidar_fov_rad").value)
            self._hsr_source = str(self.get_parameter("hsr_source").value).strip().lower()
            self._hsr_port = int(self.get_parameter("hsr_port").value)
            self._hsr_required = bool(self.get_parameter("hsr_required").value)
            self._state_port = int(self.get_parameter("state_port").value)

            # Configuration guard: cannot require HSR if no source is active
            if self._hsr_source == "none" and self._hsr_required:
                raise ValueError(
                    "Invalid configuration: hsr_required=True cannot be used with hsr_source='none'. "
                    "Set hsr_required=False for explicit obstacle-only mode."
                )

            # Node runtime state holds (AR-3: live gate parameters instantiated at startup)
            self._state = initial_state()
            self._params = get_live_gate_params(
                lidar_n_expected=self._lidar_n_expected,
                wheel_radius_mm=int(round(self._wheel_radius_m * 1000)),
                hsr_required=self._hsr_required,
            )
            self._lidar_pipeline = create_lidar_pipeline(
                n_samples=self._lidar_n_expected,
                fov_rad=self._lidar_fov_rad,
                half_width_m=self._half_width_m,
            )

            # Asynchronous HSR reflex telemetry receiver
            self._hsr_receiver = HsrReceiver(
                port=self._hsr_port,
                enabled=(self._hsr_source == "udp"),
            )

            # UDP simulation clock sender to drive synthetic producers
            self._state_sock = create_state_sender()

            self._latest_proposal: Optional[Proposal] = None
            self._proposal_seq = 0
            self._latest_ranges: Optional[List[float]] = None
            self._lidar_stamp_us: Optional[int] = None
            self._raw_valid_points: Optional[int] = None

            self._reset_requested = False
            self._hsr_status: Optional[str] = None
            self._hsr_stamp_us: Optional[int] = None

            # Subscriptions
            self._sub_cmd = self.create_subscription(
                Twist, "/cmd_vel", self._cmd_vel_callback, 10
            )
            self._sub_scan = self.create_subscription(
                LaserScan, "/scan", self._scan_callback, 10
            )
            self._sub_reset = self.create_subscription(
                String, "/gate/reset", self._reset_callback, 10
            )

            # Publishers
            self._pub_cmd_safe = self.create_publisher(Twist, "/cmd_vel_safe", 10)
            self._pub_state = self.create_publisher(String, "/gate/state", 10)

            # Deterministic 32 ms Timer (31.25 Hz)
            rate_hz = float(self.get_parameter("rate_hz").value)
            timer_period_s = 1.0 / rate_hz if rate_hz > 0.0 else 0.032
            self._timer = self.create_timer(timer_period_s, self._tick_callback)

            self.get_logger().info(
                f"QERRA Supervisory Gate Node v{NODE_VERSION} initialized. "
                f"Tick period: {timer_period_s * 1000:.1f} ms | "
                f"Lidar: {self._lidar_n_expected} beams | "
                f"HSR: source={self._hsr_source}, port={self._hsr_port}, required={self._hsr_required}"
            )

        def _get_ros_time_us(self) -> int:
            """
            Unified ROS Clock: returns current ROS time in microseconds.
            Matches the clock domain of /scan timestamps (respects use_sim_time).
            """
            return self.get_clock().now().nanoseconds // 1_000

        def _cmd_vel_callback(self, msg: Twist) -> None:
            """Receives untrusted proposed velocities and builds a causal Proposal."""
            self._proposal_seq += 1
            now_us = self._get_ros_time_us()
            try:
                self._latest_proposal = twist_to_proposal(
                    seq=self._proposal_seq,
                    sim_stamp_us=now_us,
                    linear_x_mps=float(msg.linear.x),
                    angular_z_radps=float(msg.angular.z),
                    session_id=1,
                    track_width_m=self._track_width_m,
                    wheel_radius_m=self._wheel_radius_m,
                )
            except ValueError as exc:
                self.get_logger().warn(f"Rejected invalid Twist proposal: {exc}")
                self._latest_proposal = None

        def _scan_callback(self, msg: LaserScan) -> None:
            """Ingests laser scan using fixed parameter geometry (Fail-Closed on Mismatch)."""
            if len(msg.ranges) != self._lidar_n_expected:
                self.get_logger().warn(
                    f"Scan beam mismatch: expected {self._lidar_n_expected}, "
                    f"got {len(msg.ranges)}. Discarding scan to fail closed."
                )
                self._latest_ranges = None
                self._lidar_stamp_us = None
                self._raw_valid_points = None
                return

            try:
                filtered, stamp_us, valid_pts = process_laser_scan(
                    ranges=msg.ranges,
                    stamp_sec=msg.header.stamp.sec,
                    stamp_nanosec=msg.header.stamp.nanosec,
                    pipeline=self._lidar_pipeline,
                )
                self._latest_ranges = filtered
                self._lidar_stamp_us = stamp_us
                self._raw_valid_points = valid_pts
            except Exception as exc:
                self.get_logger().error(f"Scan processing exception: {exc}. Discarding scan.")
                self._latest_ranges = None
                self._lidar_stamp_us = None
                self._raw_valid_points = None

        def _reset_callback(self, msg: String) -> None:
            """Accepts operator reset trigger."""
            if msg.data.strip().lower() == RESET_SOURCE_OPERATOR:
                self._reset_requested = True

        def _tick_callback(self) -> None:
            """Deterministic Gate evaluation tick (Fail-Closed Guarantees)."""
            try:
                now_us = self._get_ros_time_us()
                reset_source = RESET_SOURCE_OPERATOR if self._reset_requested else None
                self._reset_requested = False

                # Echo clock to synthetic producer on port 5007
                send_state(self._state_sock, now_us, port=self._state_port)

                # Poll HSR reflex telemetry stream
                self._hsr_status, self._hsr_stamp_us = self._hsr_receiver.poll(now_us)

                inputs = GateInputs(
                    sim_time_us=now_us,
                    proposal=self._latest_proposal,
                    ranges_m=self._latest_ranges,
                    lidar_stamp_us=self._lidar_stamp_us,
                    reset_source=reset_source,
                    raw_valid_points=self._raw_valid_points,
                    hsr_status=self._hsr_status,
                    hsr_stamp_us=self._hsr_stamp_us,
                )

                result = step(self._state, self._params, inputs)
                self._state = result.state

                # Actuator publication (fail-closed clamped)
                safe_linear_x, safe_angular_z = wheel_speeds_to_twist(
                    result.cmd_left_urad_s,
                    result.cmd_right_urad_s,
                    track_width_m=self._track_width_m,
                    wheel_radius_m=self._wheel_radius_m,
                )

                safe_twist = Twist()
                safe_twist.linear.x = safe_linear_x
                safe_twist.angular.z = safe_angular_z
                self._pub_cmd_safe.publish(safe_twist)

                # Publish diagnostic state telemetry (including HSR status and diagnostics)
                state_msg = String()
                state_msg.data = format_gate_state_json(
                    self._state,
                    result.record,
                    hsr_source=self._hsr_source,
                    hsr_required=self._hsr_required,
                    hsr_drained=self._hsr_receiver.packets_drained_total,
                    hsr_error=self._hsr_receiver.socket_error,
                )
                self._pub_state.publish(state_msg)

            except Exception as exc:
                # Fail-closed zeroing on any unhandled tick exception
                self.get_logger().error(f"Tick exception (holding 0.0 m/s fail-closed): {exc}")
                zero_twist = Twist()
                self._pub_cmd_safe.publish(zero_twist)

        def destroy_node(self) -> bool:
            """Releases HSR receiver and state sockets, cleaning up resources."""
            if hasattr(self, "_hsr_receiver"):
                self._hsr_receiver.close()
            if hasattr(self, "_state_sock") and self._state_sock is not None:
                try:
                    self._state_sock.close()
                except OSError:
                    pass
                self._state_sock = None
            return super().destroy_node()


def main(args=None) -> None:
    """ROS 2 node execution entry point."""
    require_ros2()
    rclpy.init(args=args)
    node = QerraGateNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Emergency fail-closed zero command on shutdown
        try:
            if rclpy.ok():
                zero_twist = Twist()
                node._pub_cmd_safe.publish(zero_twist)
        except Exception:
            pass
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
