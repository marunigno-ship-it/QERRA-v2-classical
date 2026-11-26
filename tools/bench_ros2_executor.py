# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Empirical ROS 2 SingleThreadedExecutor timing benchmark for QERRA Supervisory Gate.

Measures real rclpy scheduling jitter, callback duration, head-of-line blocking,
and flight log I/O overhead across 5 structured scenarios:
  1. Baseline empty 32 ms timer (platform noise floor)
  2. QERRA gate node idle (timer only)
  3. QERRA gate node with 682-beam scan + odom + proposal traffic
  4. QERRA gate node with live traffic AND synchronous SHA-256 flight logging
  5. Synthetic head-of-line blocking demonstration (40 ms injected scan pause)

Uses pre-allocated in-memory buffers (zero disk I/O during measurement).
Executes inside Linux ros:jazzy container CI. Exits cleanly on hosts without rclpy.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path when run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Graceful exit on hosts lacking rclpy (e.g. Windows development host)
try:
    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan

    from gate.gate_core import GATE_CORE_VERSION
    from gate.gate_log import GateLogger, capture_harness_manifest
    from ros2.qerra_gate_node import (
        DEFAULT_LIDAR_FOV_RAD,
        DEFAULT_LIDAR_N_EXPECTED,
        QerraGateNode,
    )

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False


# ----------------------------------------------------------------------------
# Statistical Utilities (Pure Python stdlib)
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
    """Converts nanosecond measurements to statistical metrics in milliseconds."""
    durations_ms = sorted(d / 1_000_000.0 for d in durations_ns if d > 0)
    n = len(durations_ms)
    if n == 0:
        return {"n": 0, "mean_ms": 0.0, "min_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}

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


# ----------------------------------------------------------------------------
# In-Memory Metrics Buffer (Pre-allocated, Zero I/O During Measurement)
# ----------------------------------------------------------------------------
class BenchmarkMetrics:
    def __init__(self, target_ticks: int):
        self.target_ticks = target_ticks
        self.tick_count = 0
        self.tick_durations_ns: List[int] = [0] * target_ticks
        self.tick_intervals_ns: List[int] = [0] * target_ticks
        self.last_tick_timestamp_ns = 0

        self.scan_count = 0
        self.scan_durations_ns: List[int] = [0] * (target_ticks * 2)

    def record_tick_start(self) -> int:
        t0 = time.perf_counter_ns()
        if self.last_tick_timestamp_ns > 0 and self.tick_count < self.target_ticks:
            self.tick_intervals_ns[self.tick_count] = t0 - self.last_tick_timestamp_ns
        self.last_tick_timestamp_ns = t0
        return t0

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

    class BaselineTimerNode(Node):
        """Node measuring empty 32 ms timer dispatch jitter (OS noise floor)."""

        def __init__(self, metrics: BenchmarkMetrics, period_s: float = 0.032):
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
        """Generates realistic 31.25 Hz LaserScan, Odometry, and Twist traffic."""

        def __init__(self, period_s: float = 0.032):
            super().__init__("benchmark_traffic_publisher_node")
            self.pub_scan = self.create_publisher(LaserScan, "/scan", qos_profile_sensor_data)
            self.pub_cmd = self.create_publisher(Twist, "/cmd_vel", 10)
            self.pub_odom = self.create_publisher(Odometry, "/odom", 10)

            self._timer = self.create_timer(period_s, self._traffic_tick)
            self._seq = 0

        def _traffic_tick(self) -> None:
            self._seq += 1
            now = self.get_clock().now().to_msg()

            # 1. 682-beam LaserScan with valid metadata
            scan = LaserScan()
            scan.header.stamp = now
            scan.header.frame_id = "base_laser_link"
            scan.angle_min = -DEFAULT_LIDAR_FOV_RAD / 2.0
            scan.angle_max = DEFAULT_LIDAR_FOV_RAD / 2.0
            scan.angle_increment = DEFAULT_LIDAR_FOV_RAD / float(DEFAULT_LIDAR_N_EXPECTED - 1)
            scan.range_min = 0.05
            scan.range_max = 5.6
            scan.ranges = [3.0] * DEFAULT_LIDAR_N_EXPECTED
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


# ----------------------------------------------------------------------------
# Scenario Execution Harness
# ----------------------------------------------------------------------------
def run_scenario(
    scenario_name: str,
    target_ticks: int,
    node_factory,
    needs_traffic: bool = False,
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
    missed_deadlines = sum(1 for d in intervals_ns if (d / 1_000_000.0) > 35.0)

    scan_stats = None
    if metrics.scan_count > 0:
        scan_stats = calculate_distribution_stats(metrics.scan_durations_ns[:metrics.scan_count])

    return {
        "scenario": scenario_name,
        "ticks": target_ticks,
        "tick_duration_ms": duration_stats,
        "inter_tick_interval_ms": interval_stats,
        "scan_duration_ms": scan_stats,
        "missed_deadlines": missed_deadlines,
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
    parser.add_argument("--ticks", type=int, default=500, help="Number of ticks per scenario (default: 500)")
    args = parser.parse_args()

    ticks = args.ticks

    print("=" * 80)
    print("  QERRA ROS 2 JAZZY EXECUTOR TIMING & CONTENTION BENCHMARK")
    print("=" * 80)
    print(f"Platform:   {platform.platform()}")
    print(f"Processor:  {platform.processor()}")
    print(f"Python:     {platform.python_implementation()} {platform.python_version()}")
    print(f"Ticks/Scen: {ticks} ticks (approx. {ticks * 0.032:.1f} s execution per scenario)")
    print("=" * 80)

    results = []

    # Scenario 1: Empty Timer Baseline
    results.append(run_scenario(
        "1. Baseline Empty 32ms Timer",
        ticks,
        lambda m: BaselineTimerNode(m, period_s=0.032),
        needs_traffic=False,
    ))

    # Scenario 2: QERRA Gate Node Idle
    results.append(run_scenario(
        "2. QERRA Gate Node (Idle, Timer Only)",
        ticks,
        lambda m: InstrumentedQerraGateNode(m),
        needs_traffic=False,
    ))

    # Scenario 3: QERRA Gate Node Under 682-beam Scan + Odom + Cmd Traffic
    results.append(run_scenario(
        "3. QERRA Gate Node (Active 682-beam Traffic)",
        ticks,
        lambda m: InstrumentedQerraGateNode(m),
        needs_traffic=True,
    ))

    # Scenario 4: QERRA Gate Node with Flight Logger Active
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "bench_flight_log.jsonl")
        results.append(run_scenario(
            "4. QERRA Gate Node (Traffic + Flight Log)",
            ticks,
            lambda m: InstrumentedQerraGateNode(m, flight_log_file=log_file),
            needs_traffic=True,
        ))

    # Scenario 5: Synthetic Head-of-Line Blocking Demonstration (40ms scan delay)
    results.append(run_scenario(
        "5. Head-of-Line Blocking (40ms Scan Delay)",
        min(100, ticks),
        lambda m: InstrumentedQerraGateNode(m, injected_scan_delay_s=0.040),
        needs_traffic=True,
    ))

    # ------------------------------------------------------------------------
    # Formatted Summary Report
    # ------------------------------------------------------------------------
    lines = []
    lines.append("\n### QERRA ROS 2 SingleThreadedExecutor Empirical Timing Results")
    lines.append(f"**Platform:** `{platform.platform()}` | **Python:** `{platform.python_version()}`\n")
    lines.append("| Scenario | Compute p50 | Compute p99 | Interval p50 | Interval p99 | Missed Deadlines (>35ms) |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

    for r in results:
        comp = r["tick_duration_ms"]
        inter = r["inter_tick_interval_ms"]
        lines.append(
            f"| {r['scenario']} | "
            f"{comp['p50_ms']:.3f} ms | "
            f"{comp['p99_ms']:.3f} ms | "
            f"{inter['p50_ms']:.3f} ms | "
            f"{inter['p99_ms']:.3f} ms | "
            f"{r['missed_deadlines']} |"
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
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"platform": platform.platform(), "results": results}, f, indent=2)
        print(f"[BENCHMARK] Exported structured results to: {json_path}")
    except Exception as exc:
        print(f"[BENCHMARK] Could not write JSON artifact: {exc}")


if __name__ == "__main__":
    main()
