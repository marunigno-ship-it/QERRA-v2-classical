# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Empirical ROS 2 SingleThreadedExecutor timing benchmark for QERRA Supervisory Gate.

Measures real rclpy scheduling jitter, expected-release dispatch lateness,
callback duration, head-of-line blocking, flight log I/O overhead, and
separate-process hazard trip software response across 6 structured scenarios:
  1. Baseline empty 32 ms timer (platform noise floor)
  2. QERRA gate node idle (timer only)
  3. QERRA gate node with 682-beam scan + odom + proposal traffic (shared-executor simulation)
  4. QERRA gate node with live traffic AND synchronous SHA-256 flight logging (shared-executor)
  5. Synthetic head-of-line blocking demonstration (40 ms injected scan pause)
  6. Separate-process hazard publisher & /cmd_vel_safe observer over 100 seeded trials
     (measures publish_call_entry_to_zero_command_receive_ms; software response only)

Uses pre-allocated in-memory buffers (zero disk I/O during Scenarios 1-3, 5-6 measurement).
Executes inside Linux ros:jazzy container CI. Exits cleanly on hosts without rclpy.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
import os
import platform
import random
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path when run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PERIOD_S = 0.032
PERIOD_NS = 32_000_000
DEADLINE_THRESHOLD_MS = 35.0
DEFAULT_TRIP_TRIALS = 100
DEFAULT_TRIP_SEED = 20261126

# Graceful exit on hosts lacking rclpy (e.g. Windows development host)
try:
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import String

    from gate.gate_core import GATE_CORE_VERSION, RESET_SOURCE_OPERATOR
    from gate.gate_log import GateLogger, capture_harness_manifest
    from ros2.qerra_gate_node import (
        DEFAULT_LIDAR_FOV_RAD,
        DEFAULT_LIDAR_N_EXPECTED,
        NODE_VERSION,
        QerraGateNode,
    )

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False


# ----------------------------------------------------------------------------
# Statistical & Provenance Utilities (Pure Python stdlib)
# ----------------------------------------------------------------------------
def percentile(sorted_data: List[float], p: float) -> float:
    """Calculates p-th percentile from sorted list using linear interpolation."""
    n = len(sorted_data)
    if n == 0:
        return 0.0
    idx = (n - 1) * p
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    weight = idx - lower
    return sorted_data[lower] * (1.0 - weight) + sorted_data[upper] * weight


def calculate_distribution_stats(durations_ns: List[int]) -> Dict[str, float]:
    """Converts strictly positive nanosecond durations to statistical metrics in ms."""
    durations_ms = sorted(d / 1_000_000.0 for d in durations_ns if d > 0)
    n = len(durations_ms)
    if n == 0:
        return {
            "n": 0,
            "mean_ms": 0.0,
            "min_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "max_ms": 0.0,
        }

    mean_val = sum(durations_ms) / n
    return {
        "n": n,
        "mean_ms": round(mean_val, 3),
        "min_ms": round(durations_ms[0], 3),
        "p50_ms": round(percentile(durations_ms, 0.50), 3),
        "p95_ms": round(percentile(durations_ms, 0.95), 3),
        "p99_ms": round(percentile(durations_ms, 0.99), 3),
        "max_ms": round(durations_ms[-1], 3),
    }


def calculate_signed_distribution_stats(values_ns: List[int]) -> Dict[str, float]:
    """Converts signed nanosecond measurements (e.g. dispatch lateness) to ms stats."""
    values_ms = sorted(v / 1_000_000.0 for v in values_ns)
    n = len(values_ms)
    if n == 0:
        return {
            "n": 0,
            "mean_ms": 0.0,
            "min_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "max_ms": 0.0,
        }

    mean_val = sum(values_ms) / n
    return {
        "n": n,
        "mean_ms": round(mean_val, 3),
        "min_ms": round(values_ms[0], 3),
        "p50_ms": round(percentile(values_ms, 0.50), 3),
        "p95_ms": round(percentile(values_ms, 0.95), 3),
        "p99_ms": round(percentile(values_ms, 0.99), 3),
        "max_ms": round(values_ms[-1], 3),
    }


def _read_linux_cpu_info() -> Dict[str, Any]:
    """Reads CPU model name and logical processor count from /proc/cpuinfo if present."""
    info: Dict[str, Any] = {
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "model_name": None,
        "proc_cpuinfo_count": 0,
    }
    cpuinfo_path = Path("/proc/cpuinfo")
    if not cpuinfo_path.is_file():
        return info
    try:
        proc_count = 0
        model_name: Optional[str] = None
        for line in cpuinfo_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("processor"):
                proc_count += 1
            elif model_name is None and (
                line.startswith("model name") or line.startswith("Hardware")
            ):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    model_name = parts[1].strip()
        info["model_name"] = model_name
        info["proc_cpuinfo_count"] = proc_count
    except OSError:
        pass
    return info


def _detect_runtime_rmw() -> str:
    """Queries the active RMW identifier inside an initialized rclpy context."""
    env_rmw = os.environ.get("RMW_IMPLEMENTATION")
    if not ROS2_AVAILABLE:
        return env_rmw or "unavailable"
    try:
        from rclpy.utilities import get_rmw_implementation_identifier

        if rclpy.ok():
            return str(get_rmw_implementation_identifier())
        rclpy.init()
        try:
            return str(get_rmw_implementation_identifier())
        finally:
            if rclpy.ok():
                rclpy.shutdown()
    except Exception:
        return env_rmw or "unknown"


def collect_provenance_metadata(
    ticks: int,
    trip_trials: int,
    trip_seed: int,
) -> Dict[str, Any]:
    """Collects full run provenance metadata for benchmark reproducibility."""
    git_sha = os.environ.get("GITHUB_SHA", "unknown")
    git_dirty: Optional[bool] = None
    try:
        sha_out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        if sha_out:
            git_sha = sha_out
        status_out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        git_dirty = bool(status_out)
    except Exception:
        pass

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_sha": git_sha,
        "git_dirty": git_dirty,
        "kernel": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "ros": {
            "ros_distro": os.environ.get("ROS_DISTRO", "unknown"),
            "rmw_implementation": _detect_runtime_rmw(),
            "rmw_env": os.environ.get("RMW_IMPLEMENTATION"),
            "ros_domain_id": os.environ.get("ROS_DOMAIN_ID", "default"),
            "node_version": NODE_VERSION if ROS2_AVAILABLE else "unavailable",
            "gate_core_version": GATE_CORE_VERSION if ROS2_AVAILABLE else "unavailable",
            "timer_info_available": False,
            "lateness_method": "monotonic_expected_release_t0_plus_k_32ms",
        },
        "cpu": _read_linux_cpu_info(),
        "run_parameters": {
            "ticks_per_executor_scenario": ticks,
            "scenario_5_ticks": min(100, ticks),
            "timer_period_ms": PERIOD_S * 1000.0,
            "missed_deadline_interval_threshold_ms": DEADLINE_THRESHOLD_MS,
            "scenario_6_trip_trials": trip_trials,
            "scenario_6_seed": trip_seed,
        },
        "classification_notes": (
            "Software timing observations only on general-purpose Linux kernel "
            "(non-RTOS container on shared virtualized CI host). Zero WCET or "
            "real-time guarantees. Physical AMR hardware count: 0."
        ),
    }


# ----------------------------------------------------------------------------
# In-Memory Metrics Buffer (Pre-allocated, Zero I/O During Measurement)
# ----------------------------------------------------------------------------
class BenchmarkMetrics:
    def __init__(self, target_ticks: int, period_ns: int = PERIOD_NS):
        self.target_ticks = target_ticks
        self.period_ns = period_ns
        self.tick_count = 0
        self.tick_durations_ns: List[int] = [0] * target_ticks
        self.tick_intervals_ns: List[int] = [0] * target_ticks
        self.tick_lateness_ns: List[int] = [0] * target_ticks
        self.t0_ns = 0
        self.last_tick_timestamp_ns = 0

        self.scan_count = 0
        self.scan_durations_ns: List[int] = [0] * (target_ticks * 2)

    def record_tick_start(self) -> int:
        t_now = time.perf_counter_ns()
        idx = self.tick_count
        if idx == 0:
            self.t0_ns = t_now
            if self.target_ticks > 0:
                self.tick_lateness_ns[0] = 0
        elif idx < self.target_ticks:
            self.tick_intervals_ns[idx] = t_now - self.last_tick_timestamp_ns
            expected_ns = self.t0_ns + idx * self.period_ns
            self.tick_lateness_ns[idx] = t_now - expected_ns
        self.last_tick_timestamp_ns = t_now
        return t_now

    def record_tick_end(self, t0: int) -> None:
        t1 = time.perf_counter_ns()
        if self.tick_count < self.target_ticks:
            self.tick_durations_ns[self.tick_count] = t1 - t0
            self.tick_count += 1

    def record_scan_duration(self, duration_ns: int) -> None:
        if self.scan_count < len(self.scan_durations_ns):
            self.scan_durations_ns[self.scan_count] = duration_ns
            self.scan_count += 1


# ----------------------------------------------------------------------------
# ROS 2 Benchmark Nodes (Active when rclpy is available)
# ----------------------------------------------------------------------------
if ROS2_AVAILABLE:

    def _build_laserscan_msg(stamp_msg: Any, ranges: List[float]) -> LaserScan:
        scan = LaserScan()
        scan.header.stamp = stamp_msg
        scan.header.frame_id = "base_laser_link"
        scan.angle_min = -DEFAULT_LIDAR_FOV_RAD / 2.0
        scan.angle_max = DEFAULT_LIDAR_FOV_RAD / 2.0
        scan.angle_increment = DEFAULT_LIDAR_FOV_RAD / float(DEFAULT_LIDAR_N_EXPECTED - 1)
        scan.range_min = 0.05
        scan.range_max = 5.6
        scan.ranges = ranges
        return scan

    class BaselineTimerNode(Node):
        """Node measuring empty 32 ms timer dispatch jitter (OS noise floor)."""

        def __init__(self, metrics: BenchmarkMetrics, period_s: float = PERIOD_S):
            super().__init__("baseline_timer_node")
            self._metrics = metrics
            self._timer = self.create_timer(period_s, self._tick_callback)

        def _tick_callback(self) -> None:
            t0 = self._metrics.record_tick_start()
            self._metrics.record_tick_end(t0)

    class InstrumentedQerraGateNode(QerraGateNode):
        """QerraGateNode subclass instrumented with in-memory latency probes."""

        def __init__(
            self,
            metrics: BenchmarkMetrics,
            *,
            flight_log_file: Optional[str] = None,
            injected_scan_delay_s: float = 0.0,
        ):
            self._metrics = metrics
            self._injected_delay_s = injected_scan_delay_s
            super().__init__()

            # Explicitly activate GateLogger if flight_log_file is provided
            if flight_log_file:
                self._flight_log_path = flight_log_file
                manifest = capture_harness_manifest()
                manifest["params"] = asdict(self._params)
                self._flight_logger = GateLogger(
                    filepath=self._flight_log_path,
                    run_id=f"bench_{self._get_ros_time_us()}",
                    gate_version=GATE_CORE_VERSION,
                    manifest=manifest,
                )

        def _scan_callback(self, msg: LaserScan) -> None:
            t0 = time.perf_counter_ns()
            if self._injected_delay_s > 0.0:
                time.sleep(self._injected_delay_s)
            super()._scan_callback(msg)
            t1 = time.perf_counter_ns()
            self._metrics.record_scan_duration(t1 - t0)

        def _tick_callback(self) -> None:
            t0 = self._metrics.record_tick_start()
            super()._tick_callback()
            self._metrics.record_tick_end(t0)

    class BenchmarkTrafficPublisherNode(Node):
        """Generates 31.25 Hz LaserScan, Odometry, and Twist traffic inside shared executor."""

        def __init__(self, period_s: float = PERIOD_S):
            super().__init__("benchmark_traffic_publisher_node")
            self.pub_scan = self.create_publisher(LaserScan, "/scan", qos_profile_sensor_data)
            self.pub_cmd = self.create_publisher(Twist, "/cmd_vel", 10)
            self.pub_odom = self.create_publisher(Odometry, "/odom", 10)

            self._clear_ranges = [3.0] * DEFAULT_LIDAR_N_EXPECTED
            self._timer = self.create_timer(period_s, self._traffic_tick)
            self._seq = 0

        def _traffic_tick(self) -> None:
            self._seq += 1
            now = self.get_clock().now().to_msg()

            # 1. 682-beam LaserScan with valid metadata
            scan = _build_laserscan_msg(now, self._clear_ranges)
            self.pub_scan.publish(scan)

            # 2. Twist Proposal
            twist = Twist()
            twist.linear.x = 0.20
            twist.angular.z = 0.0
            self.pub_cmd.publish(twist)

            # 3. Odometry
            odom = Odometry()
            odom.header.stamp = now
            odom.header.frame_id = "odom"
            odom.child_frame_id = "base_footprint"
            odom.twist.twist.linear.x = 0.20
            odom.twist.twist.angular.z = 0.0
            self.pub_odom.publish(odom)

    class HazardTrialObserverNode(Node):
        """
        Separate-process publisher and /cmd_vel_safe + /gate/state observer
        for Scenario 6 hazard trip software response measurement.
        """

        def __init__(self) -> None:
            super().__init__("hazard_trial_observer_node")
            self._lock = threading.Lock()

            self.pub_scan = self.create_publisher(LaserScan, "/scan", qos_profile_sensor_data)
            self.pub_cmd = self.create_publisher(Twist, "/cmd_vel", 10)
            self.pub_reset = self.create_publisher(String, "/gate/reset", 10)

            self.sub_cmd_safe = self.create_subscription(
                Twist, "/cmd_vel_safe", self._cmd_safe_cb, 10
            )
            self.sub_state = self.create_subscription(
                String, "/gate/state", self._state_cb, 10
            )

            self.latest_safe_twist: Optional[Twist] = None
            self.safe_twist_seq = 0
            self.latest_state_json: Optional[Dict[str, Any]] = None
            self.state_seq = 0

            # Per-trial armed measurement state
            self._trial_armed = False
            self._trial_armed_ns = 0
            self._trial_zero_recv_ns: Optional[int] = None
            self._trial_zero_lin_x: Optional[float] = None
            self._trial_zero_ang_z: Optional[float] = None
            self._trial_first_trip_reason: Optional[str] = None
            self._trial_trip_obstacle_seen = False

            self.zero_cmd_event = threading.Event()
            self.trip_obstacle_event = threading.Event()

        def _cmd_safe_cb(self, msg: Twist) -> None:
            recv_ns = time.perf_counter_ns()
            with self._lock:
                self.latest_safe_twist = msg
                self.safe_twist_seq += 1
                if (
                    self._trial_armed
                    and recv_ns >= self._trial_armed_ns
                    and self._trial_zero_recv_ns is None
                    and msg.linear.x == 0.0
                    and msg.angular.z == 0.0
                ):
                    self._trial_zero_recv_ns = recv_ns
                    self._trial_zero_lin_x = msg.linear.x
                    self._trial_zero_ang_z = msg.angular.z
                    self.zero_cmd_event.set()

        def _state_cb(self, msg: String) -> None:
            try:
                parsed = json.loads(msg.data)
            except Exception:
                parsed = None
            with self._lock:
                self.state_seq += 1
                self.latest_state_json = parsed
                if self._trial_armed and parsed is not None:
                    if parsed.get("mode") == "TRIPPED":
                        reason = parsed.get("reason")
                        if self._trial_first_trip_reason is None:
                            self._trial_first_trip_reason = reason
                        if reason == "TRIP_OBSTACLE":
                            self._trial_trip_obstacle_seen = True
                            self.trip_obstacle_event.set()

        def snapshot(self) -> Tuple[Optional[Twist], int, Optional[Dict[str, Any]], int]:
            with self._lock:
                return (
                    self.latest_safe_twist,
                    self.safe_twist_seq,
                    self.latest_state_json,
                    self.state_seq,
                )

        def arm_trial(self) -> None:
            with self._lock:
                self.zero_cmd_event.clear()
                self.trip_obstacle_event.clear()
                self._trial_zero_recv_ns = None
                self._trial_zero_lin_x = None
                self._trial_zero_ang_z = None
                self._trial_first_trip_reason = None
                self._trial_trip_obstacle_seen = False
                self._trial_armed_ns = time.perf_counter_ns()
                self._trial_armed = True

        def disarm_trial(self) -> Tuple[Optional[int], Optional[float], Optional[float], Optional[str], bool]:
            with self._lock:
                self._trial_armed = False
                return (
                    self._trial_zero_recv_ns,
                    self._trial_zero_lin_x,
                    self._trial_zero_ang_z,
                    self._trial_first_trip_reason,
                    self._trial_trip_obstacle_seen,
                )

        def get_first_trip_reason(self) -> Optional[str]:
            with self._lock:
                return self._trial_first_trip_reason

        def publish_proposal(self, linear_x: float = 0.20, angular_z: float = 0.0) -> None:
            msg = Twist()
            msg.linear.x = linear_x
            msg.angular.z = angular_z
            self.pub_cmd.publish(msg)

        def publish_scan(self, ranges: List[float]) -> None:
            now = self.get_clock().now().to_msg()
            self.pub_scan.publish(_build_laserscan_msg(now, ranges))

        def publish_reset(self, source: str = RESET_SOURCE_OPERATOR) -> None:
            msg = String()
            msg.data = source
            self.pub_reset.publish(msg)


# ----------------------------------------------------------------------------
# Scenario Execution Harness (Scenarios 1-5)
# ----------------------------------------------------------------------------
def run_scenario(
    scenario_name: str,
    target_ticks: int,
    node_factory,
    *,
    needs_traffic: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rclpy.init()
    metrics = BenchmarkMetrics(target_ticks=target_ticks)
    executor = SingleThreadedExecutor()

    node = node_factory(metrics)
    executor.add_node(node)

    traffic_node = None
    if needs_traffic:
        traffic_node = BenchmarkTrafficPublisherNode()
        executor.add_node(traffic_node)

    print(f"--> Running {scenario_name} ({target_ticks} ticks)...", flush=True)

    try:
        while metrics.tick_count < target_ticks:
            executor.spin_once(timeout_sec=0.05)
    finally:
        executor.shutdown()
        node.destroy_node()
        if traffic_node is not None:
            traffic_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    duration_stats = calculate_distribution_stats(metrics.tick_durations_ns[:target_ticks])
    intervals_ns = metrics.tick_intervals_ns[1:target_ticks]
    interval_stats = calculate_distribution_stats(intervals_ns)
    lateness_ns = metrics.tick_lateness_ns[1:target_ticks]
    lateness_stats = calculate_signed_distribution_stats(lateness_ns)
    missed_deadlines = sum(
        1 for d in intervals_ns if (d / 1_000_000.0) > DEADLINE_THRESHOLD_MS
    )

    scan_stats = None
    if metrics.scan_count > 0:
        scan_stats = calculate_distribution_stats(metrics.scan_durations_ns[:metrics.scan_count])

    return {
        "scenario": scenario_name,
        "config": config or {},
        "ticks": target_ticks,
        "tick_duration_ms": duration_stats,
        "inter_tick_interval_ms": interval_stats,
        "expected_release_lateness_ms": lateness_stats,
        "scan_duration_ms": scan_stats,
        "missed_deadlines": missed_deadlines,
        "missed_deadline_threshold_ms": DEADLINE_THRESHOLD_MS,
    }


# ----------------------------------------------------------------------------
# Scenario 6: Separate-Process Hazard Trip Software Response
# ----------------------------------------------------------------------------
def _drive_gate_to_cruise(
    observer: "HazardTrialObserverNode",
    clear_ranges: List[float],
    gate_proc: subprocess.Popen,
    timeout_s: float = 10.0,
) -> None:
    """Drives gate through clear dwell and operator reset until active cruise is confirmed."""
    _, prep_start_twist_seq, _, _ = observer.snapshot()
    deadline = time.monotonic() + timeout_s

    while True:
        if gate_proc.poll() is not None:
            raise RuntimeError(
                f"Gate subprocess exited prematurely with code {gate_proc.returncode}"
            )
        if time.monotonic() >= deadline:
            snap = observer.snapshot()
            raise RuntimeError(
                f"Timeout ({timeout_s:.1f}s) driving gate to RUN + cruise. Last snapshot: {snap}"
            )

        observer.publish_proposal(0.20, 0.0)
        observer.publish_scan(clear_ranges)

        twist, twist_seq, state, _ = observer.snapshot()
        if state is not None:
            mode = state.get("mode")
            if mode == "AWAITING_RESET":
                observer.publish_reset(RESET_SOURCE_OPERATOR)
            elif (
                mode == "RUN"
                and twist is not None
                and twist_seq > prep_start_twist_seq
                and twist.linear.x > 0.15
                and math.isclose(twist.angular.z, 0.0, abs_tol=1e-3)
            ):
                return

        time.sleep(0.025)


def run_scenario_6_hazard_trip(
    num_trials: int = DEFAULT_TRIP_TRIALS,
    seed: int = DEFAULT_TRIP_SEED,
) -> Dict[str, Any]:
    """
    Runs Scenario 6: separate-process QerraGateNode vs HazardTrialObserverNode.
    Measures publish_call_entry_to_zero_command_receive_ms across seeded
    randomized-phase hazard injections with 1.0 s dwell + operator reset recovery.
    """
    scenario_name = (
        f"6. Separate-Process Hazard Trip Response ({num_trials} Seeded Trials)"
    )
    config = {
        "topology": "separate_processes_ros2_dds_ipc",
        "gate_process_params": {
            "rate_hz": 31.25,
            "hsr_source": "none",
            "hsr_required": False,
            "standstill_required": False,
            "flight_log_path": "none",
        },
        "flight_log_enabled": False,
        "flight_log_notes": (
            "flight_log_path='none' (default node parameter; synchronous SHA-256 "
            "os.fsync() disabled to isolate DDS transport + gate software response; "
            "Scenario 4 measures fsync overhead separately)"
        ),
        "odom_enabled": False,
        "dwell_s": 1.0,
        "reset_source": RESET_SOURCE_OPERATOR,
        "target_trials": num_trials,
        "seed": seed,
        "phase_delay_uniform_s": [0.0, PERIOD_S],
        "clear_range_m": 3.0,
        "hazard_range_m": 0.15,
    }

    print(
        f"--> Running {scenario_name} (seed={seed}, flight_log_path=none)...",
        flush=True,
    )

    rng = random.Random(seed)
    clear_ranges = [3.0] * DEFAULT_LIDAR_N_EXPECTED
    hazard_ranges = [0.15] * DEFAULT_LIDAR_N_EXPECTED

    latencies_ns: List[int] = []
    pre_hazard_retries = 0
    anomalous_trials: List[Dict[str, Any]] = []
    zero_verified_count = 0
    correlated_count = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        gate_log_path = os.path.join(tmpdir, "scenario6_gate_node.log")
        child_env = os.environ.copy()
        child_env["PYTHONUNBUFFERED"] = "1"
        existing_pp = child_env.get("PYTHONPATH", "")
        if str(REPO_ROOT) not in existing_pp.split(os.pathsep):
            child_env["PYTHONPATH"] = (
                f"{REPO_ROOT}{os.pathsep}{existing_pp}" if existing_pp else str(REPO_ROOT)
            )

        gate_cmd = [
            sys.executable,
            "-m",
            "ros2.qerra_gate_node",
            "--ros-args",
            "-p", "hsr_source:=none",
            "-p", "hsr_required:=false",
            "-p", "standstill_required:=false",
            "-p", "flight_log_path:=none",
        ]

        rclpy.init()
        observer = HazardTrialObserverNode()
        executor = SingleThreadedExecutor()
        executor.add_node(observer)

        stop_event = threading.Event()
        spin_errors: List[Exception] = []

        def _spin_loop() -> None:
            try:
                while not stop_event.is_set() and rclpy.ok():
                    executor.spin_once(timeout_sec=0.01)
            except Exception as exc:
                spin_errors.append(exc)

        spin_thread = threading.Thread(target=_spin_loop, daemon=True)
        spin_thread.start()

        with open(gate_log_path, "w", encoding="utf-8") as log_fh:
            gate_proc = subprocess.Popen(
                gate_cmd,
                cwd=str(REPO_ROOT),
                env=child_env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
            )

            try:
                # Wait for initial /gate/state discovery from separate process
                disc_deadline = time.monotonic() + 10.0
                while time.monotonic() < disc_deadline:
                    if gate_proc.poll() is not None:
                        raise RuntimeError(
                            f"Gate subprocess exited during startup (code {gate_proc.returncode})"
                        )
                    _, _, state, _ = observer.snapshot()
                    if state is not None:
                        break
                    time.sleep(0.02)
                else:
                    raise RuntimeError("Timed out waiting for /gate/state discovery in Scenario 6")

                max_attempts = num_trials + 15
                attempts = 0
                while len(latencies_ns) < num_trials and attempts < max_attempts:
                    attempts += 1
                    if spin_errors:
                        raise RuntimeError(f"Observer spin thread failed: {spin_errors[0]}")

                    # 1. Drive 1.0 s dwell + operator reset to confirmed active cruise
                    _drive_gate_to_cruise(observer, clear_ranges, gate_proc)

                    # 2. Refresh inputs immediately before randomized phase sleep
                    observer.publish_proposal(0.20, 0.0)
                    observer.publish_scan(clear_ranges)

                    phase_delay_s = rng.uniform(0.0, PERIOD_S)
                    time.sleep(phase_delay_s)

                    # Guard against pre-hazard VM preemption stalling scan/proposer before injection
                    pre_twist, _, pre_state, _ = observer.snapshot()
                    if (
                        pre_state is None
                        or pre_state.get("mode") != "RUN"
                        or pre_twist is None
                        or pre_twist.linear.x <= 0.15
                    ):
                        pre_hazard_retries += 1
                        continue

                    # 3. Prepare hazard scan and arm observer before publish call entry
                    hazard_msg = _build_laserscan_msg(
                        observer.get_clock().now().to_msg(),
                        hazard_ranges,
                    )
                    observer.arm_trial()
                    t_pub_entry_ns = time.perf_counter_ns()
                    observer.pub_scan.publish(hazard_msg)

                    # 4. Wait for zero-command + TRIP_OBSTACLE correlation while keeping proposer alive
                    wait_deadline = time.monotonic() + 1.5
                    while time.monotonic() < wait_deadline:
                        if gate_proc.poll() is not None:
                            raise RuntimeError(
                                f"Gate subprocess died mid-trial (code {gate_proc.returncode})"
                            )
                        if not observer.zero_cmd_event.is_set():
                            observer.zero_cmd_event.wait(timeout=0.020)
                        elif not observer.trip_obstacle_event.is_set():
                            observer.trip_obstacle_event.wait(timeout=0.020)

                        if (
                            observer.zero_cmd_event.is_set()
                            and observer.trip_obstacle_event.is_set()
                        ):
                            break
                        first_reason = observer.get_first_trip_reason()
                        if first_reason is not None and first_reason != "TRIP_OBSTACLE":
                            break
                        observer.publish_proposal(0.20, 0.0)

                    zero_recv_ns, lin_x, ang_z, first_reason, trip_seen = observer.disarm_trial()

                    if (
                        zero_recv_ns is not None
                        and lin_x == 0.0
                        and ang_z == 0.0
                        and trip_seen
                        and first_reason == "TRIP_OBSTACLE"
                        and zero_recv_ns > t_pub_entry_ns
                    ):
                        zero_verified_count += 1
                        correlated_count += 1
                        latencies_ns.append(zero_recv_ns - t_pub_entry_ns)
                    else:
                        anomalous_trials.append(
                            {
                                "attempt": attempts,
                                "zero_received": zero_recv_ns is not None,
                                "linear_x": lin_x,
                                "angular_z": ang_z,
                                "first_trip_reason": first_reason,
                                "trip_obstacle_seen": trip_seen,
                            }
                        )

                if len(latencies_ns) < num_trials:
                    raise RuntimeError(
                        f"Scenario 6 completed only {len(latencies_ns)}/{num_trials} correlated trials "
                        f"(pre_hazard_retries={pre_hazard_retries}, anomalous={anomalous_trials})"
                    )

            except Exception:
                log_fh.flush()
                try:
                    log_tail = Path(gate_log_path).read_text(encoding="utf-8", errors="replace")[-2000:]
                    print(f"[SCENARIO 6 GATE LOG TAIL]\n{log_tail}", flush=True)
                except OSError:
                    pass
                raise
            finally:
                stop_event.set()
                if spin_thread.is_alive():
                    spin_thread.join(timeout=2.0)

                executor.shutdown()
                observer.destroy_node()
                if rclpy.ok():
                    rclpy.shutdown()

                if gate_proc.poll() is None:
                    gate_proc.send_signal(signal.SIGINT)
                    try:
                        gate_proc.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        gate_proc.terminate()
                        try:
                            gate_proc.wait(timeout=2.0)
                        except subprocess.TimeoutExpired:
                            gate_proc.kill()
                            gate_proc.wait(timeout=2.0)

    latency_stats = calculate_distribution_stats(latencies_ns)
    return {
        "scenario": scenario_name,
        "classification": "software_response_only",
        "config": config,
        "metric": "publish_call_entry_to_zero_command_receive_ms",
        "trials_completed": len(latencies_ns),
        "trials_target": num_trials,
        "pre_hazard_retries": pre_hazard_retries,
        "anomalous_non_obstacle_trips": anomalous_trials,
        "zero_command_exact_verified_count": zero_verified_count,
        "trip_obstacle_correlated_count": correlated_count,
        "latency_ms": latency_stats,
        "trial_latencies_ms": [round(v / 1_000_000.0, 3) for v in latencies_ns],
    }


def main() -> None:
    if not ROS2_AVAILABLE:
        print("=" * 80)
        print("  QERRA ROS 2 EXECUTOR TIMING BENCHMARK")
        print("=" * 80)
        print("[NOTICE] rclpy is not installed in this environment (Windows host).")
        print("This benchmark measures ROS 2 Jazzy SingleThreadedExecutor scheduling")
        print("and callback contention, which requires a Linux ROS 2 environment.")
        print("To run: execute inside the Ubuntu 24.04 (ros:jazzy) container CI.")
        print("=" * 80)
        sys.exit(0)

    parser = argparse.ArgumentParser(description="QERRA ROS 2 Executor Benchmark")
    parser.add_argument(
        "--ticks",
        type=int,
        default=500,
        help="Number of ticks per executor scenario (default: 500)",
    )
    parser.add_argument(
        "--trip-trials",
        type=int,
        default=DEFAULT_TRIP_TRIALS,
        help=f"Number of seeded trials for Scenario 6 (default: {DEFAULT_TRIP_TRIALS})",
    )
    parser.add_argument(
        "--trip-seed",
        type=int,
        default=DEFAULT_TRIP_SEED,
        help=f"PRNG seed for Scenario 6 phase randomization (default: {DEFAULT_TRIP_SEED})",
    )
    args = parser.parse_args()

    ticks = args.ticks
    if ticks <= 0:
        raise ValueError(f"--ticks must be positive, got {ticks}")
    if args.trip_trials <= 0:
        raise ValueError(f"--trip-trials must be positive, got {args.trip_trials}")

    provenance = collect_provenance_metadata(ticks, args.trip_trials, args.trip_seed)

    print("=" * 80)
    print("  QERRA ROS 2 JAZZY EXECUTOR TIMING & CONTENTION BENCHMARK")
    print("=" * 80)
    print(f"Commit SHA: {provenance['git_commit_sha']}")
    print(f"Kernel:     {provenance['kernel']['platform']}")
    print(f"CPU:        {provenance['cpu'].get('model_name') or provenance['cpu'].get('processor')} ({provenance['cpu'].get('cpu_count')} vCPUs)")
    print(f"Python:     {provenance['python']['implementation']} {provenance['python']['version']}")
    print(f"ROS / RMW:  {provenance['ros']['ros_distro']} / {provenance['ros']['rmw_implementation']}")
    print(f"Ticks/Scen: {ticks} ticks (~{ticks * PERIOD_S:.1f} s) | Scenario 6 Trials: {args.trip_trials} (seed={args.trip_seed})")
    print("=" * 80)

    results = []

    # Scenario 1: Empty Timer Baseline
    results.append(run_scenario(
        "1. Baseline Empty 32ms Timer",
        ticks,
        lambda m: BaselineTimerNode(m, period_s=PERIOD_S),
        needs_traffic=False,
        config={
            "executor": "SingleThreadedExecutor",
            "topology": "single_node_empty_timer",
            "period_ms": PERIOD_S * 1000.0,
        },
    ))

    # Scenario 2: QERRA Gate Node Idle
    results.append(run_scenario(
        "2. QERRA Gate Node (Idle, Timer Only)",
        ticks,
        lambda m: InstrumentedQerraGateNode(m),
        needs_traffic=False,
        config={
            "executor": "SingleThreadedExecutor",
            "topology": "single_node_idle",
            "period_ms": PERIOD_S * 1000.0,
            "flight_log_enabled": False,
        },
    ))

    # Scenario 3: QERRA Gate Node Under 682-beam Scan + Odom + Cmd Traffic (Shared-Executor Simulation)
    results.append(run_scenario(
        "3. QERRA Gate Node (Active 682-beam Traffic, Shared-Executor Simulation)",
        ticks,
        lambda m: InstrumentedQerraGateNode(m),
        needs_traffic=True,
        config={
            "executor": "SingleThreadedExecutor",
            "topology": "shared_executor_same_process",
            "period_ms": PERIOD_S * 1000.0,
            "traffic_hz": 1.0 / PERIOD_S,
            "beams": DEFAULT_LIDAR_N_EXPECTED,
            "flight_log_enabled": False,
        },
    ))

    # Scenario 4: QERRA Gate Node with Flight Logger Active
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "bench_flight_log.jsonl")
        results.append(run_scenario(
            "4. QERRA Gate Node (Active Traffic + Sync SHA-256 Flight Log, Shared-Executor)",
            ticks,
            lambda m: InstrumentedQerraGateNode(m, flight_log_file=log_file),
            needs_traffic=True,
            config={
                "executor": "SingleThreadedExecutor",
                "topology": "shared_executor_same_process",
                "period_ms": PERIOD_S * 1000.0,
                "traffic_hz": 1.0 / PERIOD_S,
                "beams": DEFAULT_LIDAR_N_EXPECTED,
                "flight_log_enabled": True,
                "flight_log_sync": "os.fsync",
            },
        ))

    # Scenario 5: Synthetic Head-of-Line Blocking Demonstration (40ms scan delay)
    results.append(run_scenario(
        "5. Head-of-Line Blocking (40ms Scan Delay, Shared-Executor)",
        min(100, ticks),
        lambda m: InstrumentedQerraGateNode(m, injected_scan_delay_s=0.040),
        needs_traffic=True,
        config={
            "executor": "SingleThreadedExecutor",
            "topology": "shared_executor_same_process",
            "period_ms": PERIOD_S * 1000.0,
            "injected_scan_delay_ms": 40.0,
            "flight_log_enabled": False,
        },
    ))

    # Scenario 6: Separate-Process Hazard Publisher & /cmd_vel_safe Observer
    scenario_6 = run_scenario_6_hazard_trip(
        num_trials=args.trip_trials,
        seed=args.trip_seed,
    )

    # ------------------------------------------------------------------------
    # Formatted Summary Report
    # ------------------------------------------------------------------------
    lines = []
    lines.append("\n### QERRA ROS 2 SingleThreadedExecutor Empirical Timing Results")
    lines.append(
        f"**Commit:** `{provenance['git_commit_sha'][:12]}` | "
        f"**Kernel:** `{provenance['kernel']['platform']}` | "
        f"**Python:** `{provenance['python']['version']}` | "
        f"**RMW:** `{provenance['ros']['rmw_implementation']}`\n"
    )
    lines.append(
        "> *Software timing observations only on non-RTOS Linux CI container; "
        "no WCET or real-time guarantees.*\n"
    )
    lines.append(
        "| Scenario | Compute p50 / p99 | Interval p50 / p99 | Lateness (t0+k*32ms) p50 / p99 / max | Missed (>35ms) |"
    )
    lines.append("| :--- | :--- | :--- | :--- | :--- |")

    for r in results:
        comp = r["tick_duration_ms"]
        inter = r["inter_tick_interval_ms"]
        late = r["expected_release_lateness_ms"]
        lines.append(
            f"| {r['scenario']} | "
            f"{comp['p50_ms']:.3f} / {comp['p99_ms']:.3f} ms | "
            f"{inter['p50_ms']:.3f} / {inter['p99_ms']:.3f} ms | "
            f"{late['p50_ms']:.3f} / {late['p99_ms']:.3f} / {late['max_ms']:.3f} ms | "
            f"{r['missed_deadlines']} |"
        )

    s6_lat = scenario_6["latency_ms"]
    lines.append("\n### Scenario 6: Separate-Process Hazard Trip Latency (Software Response Only)")
    lines.append(
        f"- **Metric:** `{scenario_6['metric']}` (separate-process ROS 2 DDS pub/sub, "
        f"`flight_log_path=none`, `hsr_source=none`, `odom_enabled=False`)"
    )
    lines.append(
        f"- **Trials:** `{scenario_6['trials_completed']}/{scenario_6['trials_target']}` "
        f"(seed=`{args.trip_seed}`, uniform `[0, 32) ms` randomized phase, `1.0 s` dwell + `"
        f"{RESET_SOURCE_OPERATOR}` reset)"
    )
    lines.append(
        f"- **Verification:** `{scenario_6['zero_command_exact_verified_count']}` exact `(0.0, 0.0)` Twist "
        f"| `{scenario_6['trip_obstacle_correlated_count']}` `/gate/state TRIP_OBSTACLE` correlated "
        f"| pre-hazard retries: `{scenario_6['pre_hazard_retries']}` "
        f"| anomalous: `{len(scenario_6['anomalous_non_obstacle_trips'])}`"
    )
    lines.append(
        f"- **Latency (Software Response Only):** "
        f"**p50 = {s6_lat['p50_ms']:.3f} ms**, "
        f"**p95 = {s6_lat['p95_ms']:.3f} ms**, "
        f"**max = {s6_lat['max_ms']:.3f} ms** "
        f"(min={s6_lat['min_ms']:.3f} ms, mean={s6_lat['mean_ms']:.3f} ms)"
    )

    report_md = "\n".join(lines)
    print(report_md)

    # Also write to GitHub Step Summary if running in GitHub Actions
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as sf:
                sf.write(report_md + "\n")
        except Exception:
            pass

    json_path = os.path.join(REPO_ROOT, "tools", "benchmark_executor_results.json")
    output_payload = {
        "schema_version": "2.0",
        "classification": "software_response_only_non_rtos",
        "platform": platform.platform(),
        "provenance": provenance,
        "results": results,
        "scenario_6_hazard_trip_latency": scenario_6,
    }
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, indent=2)
        print(f"[BENCHMARK] Exported structured results to: {json_path}")
    except Exception as exc:
        print(f"[BENCHMARK] Could not write JSON artifact: {exc}")


if __name__ == "__main__":
    main()
