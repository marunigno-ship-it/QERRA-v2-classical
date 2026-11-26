# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Bare-metal CPU execution benchmark for QERRA Layer 1A Core and LiDAR pipelines.

Measures pure computational execution time (nanoseconds/microseconds) using
high-resolution monotonic hardware timers (time.perf_counter_ns()) across
>= 100,000 iterations.

Pure Python standard library only. Zero external dependencies. Runs on any host.
"""
from __future__ import annotations

import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List

# Ensure repository root is on sys.path when run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gate.gate_config import get_live_gate_params
from gate.gate_core import GateInputs, GateState, Mode, Proposal, initial_state, step
from gate.gate_lidar import CorridorFilter, LidarPipeline
from ros2.qerra_gate_node import (
    DEFAULT_LIDAR_FOV_RAD,
    DEFAULT_LIDAR_N_EXPECTED,
    process_laser_scan,
    validate_laserscan_metadata,
)

DEFAULT_ITERATIONS = 100_000
WARMUP_ITERATIONS = 5_000


def percentile(sorted_data: List[float], p: float) -> float:
    """Calculates the p-th percentile from sorted data using linear interpolation."""
    n = len(sorted_data)
    if n == 0:
        return 0.0
    idx = (n - 1) * p
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    weight = idx - lower
    return sorted_data[lower] * (1.0 - weight) + sorted_data[upper] * weight


def collect_stats(durations_ns: List[int]) -> Dict[str, float]:
    """Computes statistical distribution metrics in microseconds (us)."""
    durations_us = sorted(d / 1_000.0 for d in durations_ns)
    n = len(durations_us)
    mean_val = sum(durations_us) / n
    variance = sum((x - mean_val) ** 2 for x in durations_us) / n
    std_dev = math.sqrt(variance)

    return {
        "n": n,
        "mean_us": round(mean_val, 3),
        "std_dev_us": round(std_dev, 3),
        "min_us": round(durations_us[0], 3),
        "p50_us": round(percentile(durations_us, 0.50), 3),
        "p95_us": round(percentile(durations_us, 0.95), 3),
        "p99_us": round(percentile(durations_us, 0.99), 3),
        "p999_us": round(percentile(durations_us, 0.999), 3),
        "max_us": round(durations_us[-1], 3),
    }


def make_duck_scan(n: int = DEFAULT_LIDAR_N_EXPECTED, fov: float = DEFAULT_LIDAR_FOV_RAD):
    """Constructs a valid duck-typed LaserScan message."""
    angle_min = -fov / 2.0
    angle_max = fov / 2.0
    return SimpleNamespace(
        angle_min=angle_min,
        angle_max=angle_max,
        angle_increment=(angle_max - angle_min) / (n - 1),
        range_min=0.05,
        range_max=5.6,
        ranges=[3.0] * n,
        header=SimpleNamespace(
            frame_id="base_laser_link",
            stamp=SimpleNamespace(sec=10, nanosec=500_000_000),
        ),
    )


def run_benchmark(
    name: str,
    fn: Callable[[], Any],
    iterations: int = DEFAULT_ITERATIONS,
    warmup: int = WARMUP_ITERATIONS,
) -> Dict[str, float]:
    """Runs warmup and timed iterations, returning statistics in microseconds."""
    for _ in range(warmup):
        fn()

    durations_ns: List[int] = [0] * iterations
    timer = time.perf_counter_ns

    for i in range(iterations):
        t0 = timer()
        fn()
        t1 = timer()
        durations_ns[i] = t1 - t0

    return collect_stats(durations_ns)


def main() -> None:
    print("=" * 80)
    print("  QERRA LAYER 1A & LIDAR CPU EXECUTION BENCHMARK")
    print("=" * 80)

    # 1. Capture Environment Fingerprint
    env_info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "iterations": DEFAULT_ITERATIONS,
        "warmup": WARMUP_ITERATIONS,
    }
    print(f"Host OS:          {env_info['platform']}")
    print(f"Processor:        {env_info['processor']}")
    print(f"Python:           {env_info['python_implementation']} {env_info['python_version']}")
    print(f"Iterations:       {env_info['iterations']:,} per benchmark (Warmup: {env_info['warmup']:,})")
    print("-" * 80)

    # 2. Setup Fixtures
    params = get_live_gate_params(
        lidar_n_expected=DEFAULT_LIDAR_N_EXPECTED,
        dt_us=32_000,
        hsr_required=False,
    )
    state = GateState(mode=Mode.RUN, last_tick_us=1_000_000)
    proposal = Proposal(seq=1, sim_stamp_us=1_032_000, left_urad_s=2_040_816, right_urad_s=2_040_816)
    clear_corridor = [3.0] * DEFAULT_LIDAR_N_EXPECTED
    inp = GateInputs(
        sim_time_us=1_032_000,
        proposal=proposal,
        ranges_m=clear_corridor,
        lidar_stamp_us=1_032_000,
        meas_left_urad_s=2_040_816,
        meas_right_urad_s=2_040_816,
    )

    corridor = CorridorFilter(n_samples=DEFAULT_LIDAR_N_EXPECTED, fov_rad=DEFAULT_LIDAR_FOV_RAD, half_width_m=0.32)
    pipeline = LidarPipeline(corridor=corridor)
    raw_scan = [3.0] * DEFAULT_LIDAR_N_EXPECTED
    duck_scan = make_duck_scan()

    results: Dict[str, Dict[str, float]] = {}

    # Benchmark 1: Core step() under nominal cruise
    print("[1/4] Benchmarking gate_core.step() (Integer envelope + hazard eval)...")
    results["gate_core.step"] = run_benchmark("gate_core.step", lambda: step(state, params, inp))

    # Benchmark 2: 10-point LaserScan metadata validation
    print("[2/4] Benchmarking validate_laserscan_metadata() (10 invariant checks)...")
    results["validate_laserscan_metadata"] = run_benchmark(
        "validate_laserscan_metadata",
        lambda: validate_laserscan_metadata(duck_scan, DEFAULT_LIDAR_N_EXPECTED, DEFAULT_LIDAR_FOV_RAD),
    )

    # Benchmark 3: CorridorFilter.apply() (Trigonometric projection over 682 beams)
    print("[3/4] Benchmarking CorridorFilter.apply() (682 beams + REP-117 bounds)...")
    results["CorridorFilter.apply"] = run_benchmark(
        "CorridorFilter.apply",
        lambda: corridor.apply(raw_scan, range_min=0.05, range_max=5.6),
    )

    # Benchmark 4: Complete process_laser_scan() pipeline
    print("[4/4] Benchmarking process_laser_scan() pipeline (Ingestion + F1 + REP-117)...")
    results["process_laser_scan"] = run_benchmark(
        "process_laser_scan",
        lambda: process_laser_scan(raw_scan, 1, 0, pipeline, range_min=0.05, range_max=5.6),
    )

    print("=" * 80)
    print("  EMPIRICAL BENCHMARK RESULTS (Microseconds / us)")
    print("=" * 80)
    header = f"{'Benchmark Function':<30} | {'p50 (us)':<9} | {'p95 (us)':<9} | {'p99 (us)':<9} | {'p99.9 (us)':<10} | {'Max (us)':<9}"
    print(header)
    print("-" * len(header))
    for bench_name, s in results.items():
        row = (
            f"{bench_name:<30} | "
            f"{s['p50_us']:<9.2f} | "
            f"{s['p95_us']:<9.2f} | "
            f"{s['p99_us']:<9.2f} | "
            f"{s['p999_us']:<10.2f} | "
            f"{s['max_us']:<9.2f}"
        )
        print(row)
    print("=" * 80)

    # Architectural Budget Analysis
    tick_budget_us = 32_000.0  # 32 ms tick at 31.25 Hz
    total_compute_p99 = (
        results["gate_core.step"]["p99_us"]
        + results["validate_laserscan_metadata"]["p99_us"]
        + results["process_laser_scan"]["p99_us"]
    )
    budget_pct = (total_compute_p99 / tick_budget_us) * 100.0

    print(f"Total Cumulative p99 Compute: {total_compute_p99:.2f} us ({total_compute_p99 / 1000.0:.3f} ms)")
    print(f"32 ms Tick Budget Utilization: {budget_pct:.3f}% (Margin remaining: {100.0 - budget_pct:.2f}%)")
    print("=" * 80)


if __name__ == "__main__":
    main()
