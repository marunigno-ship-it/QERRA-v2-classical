# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- Webots robot controller (Demo 7/8/9), version 0.3.
SAFETY_CONCEPT.md v0.2: AR-1, AR-4, AR-5, AR-7, C-1, C-2, C-3, C-6, D-2, D-5.

The only process that writes wheel velocities. The untrusted proposer runs as a separate
OS process and can only send datagrams.

Integrated with QERRA-HSR assistive reflex layer.

LIVE MODE ONLY. The gate listens for proposals without ever blocking. Wall-clock exchange with a
sim-time watchdog is valid only when Webots runs at about 1x real time (use the Real-Time
button). Reproducible sweeps (T-03) need the lockstep harness, which is a later step.

Optional environment variables:
  QERRA_ROOT               repository root (override directory discovery)
  QERRA_RUN_ID             run identifier (default RUN_<epoch seconds>)
  QERRA_PROPOSER_FAULT     none | hang | die | nan | oversized      (default none)
  QERRA_FAULT_SIM_S        sim time of the fault in seconds          (default 3.0)
  QERRA_HANG_MS            hang length in ms of sim time             (default 800)
  QERRA_LIDAR_FAULT        none | freeze | stale | blind             (default none)
  QERRA_LIDAR_FAULT_SIM_S  sim time of lidar fault in seconds        (default 3.0)
  QERRA_HSR_EVENT          none | distress | hazard                  (default distress)
  QERRA_HSR_EVENT_SIM_S    sim time of HSR event in seconds          (default 4.0)
  QERRA_HSR_EVENT_END_SIM_S harness only: sim time (s) at which the injected HSR event stops
                           (distress drops back to 0.0 / hazard flag cleared); default: 7.0
  QERRA_AUTO_RESET_AT_US   harness only: inject an "operator" reset from this sim time on
                           (retried every tick until the gate answers RESET_ACCEPTED); default: 1200000
  QERRA_AUTO_RESET2_AT_US  harness only: inject ONE further "operator" reset at the first tick
                           at or after this sim time (used to test reset refusal under hazard); default: 5000000
  QERRA_AUTO_RESET3_AT_US  harness only: inject "operator" reset requests from this sim time on,
                           RETRIED every QERRA_AUTO_RESET3_PERIOD_US (default: every tick)
                           until the gate answers RESET_ACCEPTED (recovery after a hazard); default: 8200000
  QERRA_AUTO_RESET3_PERIOD_US harness only: retry period for reset 3 in microseconds
  QERRA_END_AT_S           harness only: leave the control loop at this sim time so the audit
                           log is closed cleanly (default: 14.0)
  QERRA_HSR_LOG            "1" = keep the per-tick INFO logging of the HSR module (default off)
  QERRA_SMOKE_OBSTACLE     "1" = moves DEF OBSTACLE itself (default: "0")
  QERRA_SKIP_PROPOSER      "1" = do not spawn the proposer (start it by hand)
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import logging
import math
import os
import subprocess
import sys
import time


def find_project_root() -> str:
    """Locates the QERRA-v2-classical repository root containing gate/ portably."""
    env = os.environ.get("QERRA_ROOT")
    if env and os.path.isdir(os.path.join(env, "gate")):
        return os.path.abspath(env)

    # Walk up from this controller file to find the directory containing gate/
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, "gate")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    raise RuntimeError(
        "Cannot find repository root containing gate/. "
        "Set the QERRA_ROOT environment variable to the repository root."
    )


PROJECT_ROOT = find_project_root()
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Defaults to "0" so smoke obstacle does not move into the lane during Scenario B
SMOKE_OBSTACLE = os.environ.get("QERRA_SMOKE_OBSTACLE", "0") == "1"
if SMOKE_OBSTACLE:
    try:
        from controller import Supervisor as RobotClass
    except ImportError:
        # Standalone lint/test fallback when executed outside Webots runtime
        RobotClass = object
else:
    try:
        from controller import Robot as RobotClass
    except ImportError:
        RobotClass = object

from gate.gate_config import get_live_gate_params             # noqa: E402
from gate.gate_core import (                                # noqa: E402
    GATE_CORE_VERSION, GateInputs, GateParams, Mode, Reason, RESET_SOURCE_OPERATOR, initial_state, step,
)
from gate.gate_ipc import create_udp_receiver, drain_proposals, poll_operator_reset   # noqa: E402
from gate.gate_lidar import CorridorFilter, LidarPipeline  # noqa: E402
from gate.gate_link import DEFAULT_STATE_PORT, create_state_sender, send_state   # noqa: E402
from gate.gate_log import (                                 # noqa: E402
    GateLogger, capture_harness_manifest, write_run_manifest,
)
from hsr.hysteresis_wrapper import StabilizedHSR             # noqa: E402
from hsr.qerra_hsr import HSRInput                          # noqa: E402

# ----------------------------------------------------------------------------------------
# PARAMETERS: TIAGo Base Physical Dimensions & Kinematics
# ----------------------------------------------------------------------------------------
WHEEL_RADIUS_MM = 98                 # TIAGo base wheel radius (98 mm)
ROBOT_HALF_WIDTH_M = 0.27 + 0.05     # half of ~0.54 m base width + 5 cm margin = 0.32 m
W_MAX_URAD_S = 3_000_000             # 3.0 rad/s velocity envelope cap
A_DESIGN_MMPS2 = 500                 # 0.5 m/s² design deceleration
MARGIN_MM = 300                      # 300 mm safety standoff margin
MIN_RAW_LIDAR_RETURNS = 5            # Minimum valid raw returns required for sensor liveness
PROPOSER_SPEED_URAD_S = 2_000_000    # 2.0 rad/s proposed cruise speed (approx 0.20 m/s)
OBSTACLE_AT_S = 3.5                  # Smoke test: cart moves into lane at t = 3.5s
OBSTACLE_POS = [2.8, 0.0, 0.0]       # Cart position: flat on the floor (Z = 0.0)

LIDAR_FAULT = os.environ.get("QERRA_LIDAR_FAULT", "none")
LIDAR_FAULT_SIM_S = float(os.environ.get("QERRA_LIDAR_FAULT_SIM_S", "3.0"))

HSR_EVENT = os.environ.get("QERRA_HSR_EVENT", "distress")
HSR_EVENT_SIM_S = float(os.environ.get("QERRA_HSR_EVENT_SIM_S", "4.0"))
_hsr_end_raw = os.environ.get("QERRA_HSR_EVENT_END_SIM_S", "7.0")
HSR_EVENT_END_SIM_S = float(_hsr_end_raw) if _hsr_end_raw not in (None, "") else None

PROPOSAL_PORT = 5005
OPERATOR_PORT = 5006


def env_int(name: str):
    raw = os.environ.get(name)
    return int(raw) if raw not in (None, "") else None


def compute_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_critical_code_hashes(root: str) -> dict[str, str]:
    critical_files = {
        "gate_core": os.path.join(root, "gate", "gate_core.py"),
        "gate_lidar": os.path.join(root, "gate", "gate_lidar.py"),
        "gate_ipc": os.path.join(root, "gate", "gate_ipc.py"),
        "gate_log": os.path.join(root, "gate", "gate_log.py"),
        "verify_log": os.path.join(root, "verify_log.py"),
        "proposer": os.path.join(root, "scripts", "untrusted_proposer.py"),
        "controller": os.path.abspath(__file__),
    }
    hashes = {}
    for name, path in critical_files.items():
        if os.path.isfile(path):
            hashes[name] = compute_file_sha256(path)
    return hashes


def find_lidar(robot):
    """Detects the onboard Hokuyo lidar sensor."""
    names, cands = [], []
    for i in range(robot.getNumberOfDevices()):
        dev = robot.getDeviceByIndex(i)
        names.append(dev.getName())
        low = dev.getName().lower()
        if "hokuyo" in low or "lidar" in low or "laser" in low:
            cands.append(dev)
    print(f"[GATE SENSORS] devices found on TIAGo: {names}")
    if not cands:
        raise RuntimeError("No lidar device found on robot. Check lidarSlot in world.")
    if len(cands) > 1:
        print(f"[GATE SENSORS] Multiple lidar candidates: {[c.getName() for c in cands]}. Using '{cands[0].getName()}'.")
    print(f"[GATE SENSORS] Lidar connected: '{cands[0].getName()}'")
    return cands[0]


def zero_wheels(left, right):
    """
    Fail-closed actuator clamping. Ensures both motors are commanded
    to 0.0 rad/s independently so a failure on one does not abandon the other.
    """
    errors = []
    if left is not None:
        try:
            left.setVelocity(0.0)
        except Exception as exc:
            errors.append(f"left: {exc}")
    if right is not None:
        try:
            right.setVelocity(0.0)
        except Exception as exc:
            errors.append(f"right: {exc}")
    if errors:
        sys.stderr.write(f"[ACTUATOR FAULT] zero_wheels failure: {', '.join(errors)}\n")


def percentile(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    idx = min(len(sorted_vals) - 1, max(0, int(math.ceil(q * len(sorted_vals))) - 1))
    return sorted_vals[idx]


def main():
    # Silence the per-tick (32 ms) INFO output of the HSR module.
    if os.environ.get("QERRA_HSR_LOG") != "1":
        logging.disable(logging.INFO)

    robot = RobotClass()
    timestep = int(robot.getBasicTimeStep())
    dt_us = timestep * 1000
    dt_s = timestep / 1000.0

    # 1. Actuators & Diagnostic Wheel Position Sensors
    left_motor = robot.getDevice("wheel_left_joint")
    right_motor = robot.getDevice("wheel_right_joint")
    if left_motor is None or right_motor is None:
        raise RuntimeError("wheel_left_joint / wheel_right_joint not found on this robot.")
    left_motor.setPosition(float("inf"))
    right_motor.setPosition(float("inf"))
    zero_wheels(left_motor, right_motor)
    max_vel = min(left_motor.getMaxVelocity(), right_motor.getMaxVelocity())
    w_max_urad_s = min(W_MAX_URAD_S, int(max_vel * 1_000_000))
    print(f"[GATE ACTUATORS] Motor max: {max_vel:.2f} rad/s -> Gate cap: {w_max_urad_s / 1e6:.2f} rad/s")

    # Diagnostic Position Sensors
    left_sensor = left_motor.getPositionSensor()
    if left_sensor is None:
        try:
            left_sensor = robot.getDevice("wheel_left_joint_sensor")
        except Exception:
            left_sensor = None

    right_sensor = right_motor.getPositionSensor()
    if right_sensor is None:
        try:
            right_sensor = robot.getDevice("wheel_right_joint_sensor")
        except Exception:
            right_sensor = None

    if left_sensor:
        left_sensor.enable(timestep)
    if right_sensor:
        right_sensor.enable(timestep)

    # 2. Smoke-test obstacle handle
    obstacle_trans, obstacle_injected = None, False
    if SMOKE_OBSTACLE:
        node = robot.getFromDef("OBSTACLE")
        obstacle_trans = node.getField("translation") if node else None
        print("[GATE] Obstacle injection enabled (DEF OBSTACLE will move at t = 3.5s).")

    # 3. Lidar & Corridor Filter Pipeline
    lidar = find_lidar(robot)
    lidar.enable(timestep)
    resolution = lidar.getHorizontalResolution()
    fov = lidar.getFov()
    corridor = CorridorFilter(resolution, fov, ROBOT_HALF_WIDTH_M)
    lidar_pipeline = LidarPipeline(corridor=corridor)
    print(f"[GATE SENSORS] Lidar resolution={resolution}, FOV={math.degrees(fov):.0f}°, Corridor width={ROBOT_HALF_WIDTH_M * 2:.2f}m")
    if LIDAR_FAULT != "none":
        print(f"[GATE SENSORS] Lidar fault '{LIDAR_FAULT}' scheduled at sim t={LIDAR_FAULT_SIM_S:.2f}s")

    # 4. QERRA-HSR Reflex Companion (Clock synchronized strictly to Webots simulation time)
    sim_clock_s = 0.0
    hsr_companion = StabilizedHSR(clock=lambda: sim_clock_s)
    if HSR_EVENT != "none":
        _end_txt = f", ends at sim t={HSR_EVENT_END_SIM_S:.2f}s" if HSR_EVENT_END_SIM_S is not None else ""
        print(f"[GATE HSR] Injected HSR event '{HSR_EVENT}' scheduled at sim t={HSR_EVENT_SIM_S:.2f}s{_end_txt}")

    # 5. Inputs & Non-blocking Sockets
    keyboard = robot.getKeyboard()
    keyboard.enable(timestep)
    prop_sock = create_udp_receiver(port=PROPOSAL_PORT)
    op_sock = create_udp_receiver(port=OPERATOR_PORT)
    state_sock = create_state_sender()

    # 6. Gate Parameters (Fail-closed HSR reflex layer explicitly required)
    params = get_live_gate_params(
        lidar_n_expected=resolution,
        dt_us=dt_us,
        w_max_urad_s=w_max_urad_s,
        t_react_us=32_000,
        hsr_required=True,
    )
    state = initial_state()

    # 7. Flight Recorder, Telemetry & Harness Manifest
    run_id = os.environ.get("QERRA_RUN_ID") or "DEMO9_SCENARIO_B_FINAL"
    run_dir = os.path.join(PROJECT_ROOT, "results", run_id)
    os.makedirs(run_dir, exist_ok=True)

    # Effective QERRA_* configuration as this process actually sees it
    qerra_env = {k: v for k, v in sorted(os.environ.items()) if k.startswith("QERRA_")}

    manifest = capture_harness_manifest()
    manifest["run_id"] = run_id
    manifest["gate_version"] = GATE_CORE_VERSION
    manifest["params"] = asdict(params)
    manifest["code_hashes"] = get_critical_code_hashes(PROJECT_ROOT)
    manifest["qerra_env"] = qerra_env
    manifest_path = write_run_manifest(run_dir, manifest)

    log_path = os.path.join(run_dir, "gate_audit.jsonl")
    telemetry_path = os.path.join(run_dir, "wheel_telemetry.csv")

    logger = GateLogger(log_path, run_id=run_id, gate_version=GATE_CORE_VERSION, manifest=manifest)

    telemetry_file = open(telemetry_path, "w", encoding="utf-8", newline="\n")
    telemetry_file.write("sim_time_sec,cmd_left_rad_s,cmd_right_rad_s,meas_left_rad_s,meas_right_rad_s,lidar_min_mm\n")

    # 8. Untrusted Proposer
    proposer_proc = None
    proposer_warned = False
    proposer_script = os.path.join(PROJECT_ROOT, "scripts", "untrusted_proposer.py")
    if os.environ.get("QERRA_SKIP_PROPOSER") != "1" and os.path.isfile(proposer_script):
        cmd = [
            sys.executable, "-u", proposer_script,
            "--port", str(PROPOSAL_PORT), "--state-port", str(DEFAULT_STATE_PORT),
            "--speed", str(PROPOSER_SPEED_URAD_S),
            "--fault", os.environ.get("QERRA_PROPOSER_FAULT", "none"),
            "--fault-sim-s", os.environ.get("QERRA_FAULT_SIM_S", "3.0"),
            "--hang-ms", os.environ.get("QERRA_HANG_MS", "800"),
        ]
        proposer_proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT)

    auto_reset_at_us = env_int("QERRA_AUTO_RESET_AT_US") or 1_200_000
    auto_reset_done = False
    auto_reset2_at_us = env_int("QERRA_AUTO_RESET2_AT_US") or 5_000_000
    auto_reset2_done = False
    auto_reset3_at_us = env_int("QERRA_AUTO_RESET3_AT_US") or 8_200_000
    auto_reset3_period_us = env_int("QERRA_AUTO_RESET3_PERIOD_US") or dt_us
    auto_reset3_next_us = auto_reset3_at_us
    auto_reset3_done = False
    end_at_raw = os.environ.get("QERRA_END_AT_S", "14.0")
    end_at_us = int(float(end_at_raw) * 1_000_000) if end_at_raw else None

    print("\n" + "=" * 70)
    print(f"QERRA Supervisory Gate v{GATE_CORE_VERSION} -- LIVE MODE (HSR COMPANION ACTIVE)")
    print(f"  • Run ID         : {run_id}")
    print(f"  • Manifest       : {manifest_path}")
    print(f"  • Flight Recorder: {log_path}")
    print(f"  • Telemetry CSV  : {telemetry_path}")
    print(f"  • AI Brain (PID) : {proposer_proc.pid if proposer_proc else 'Manual'}")
    print(f"  • Proposal Port  : {PROPOSAL_PORT} | Reset Port: {OPERATOR_PORT} | State Port: {DEFAULT_STATE_PORT}")
    print(f"  • Smoke obstacle : {'ENABLED' if SMOKE_OBSTACLE else 'disabled'}")
    print("  • QERRA_* env seen by this controller:")
    if qerra_env:
        for k, v in qerra_env.items():
            print(f"      {k}={v}")
    else:
        print("      (defaults active for Scenario B)")
    print("  • START SEQUENCE : Auto-reset armed (hands-free)")
    print("=" * 70 + "\n")

    tick = 0
    log_failed_prev = False
    lidar_fault_triggered = False
    last_mode, last_reason = None, None
    last_hsr_status = None
    last_reset_print = None
    compute_ns = []
    wall_intervals_ms = []
    last_tick_wall_ns = None

    prev_pos_left = None
    prev_pos_right = None
    prev_key_r_down = False

    try:
        while robot.step(timestep) != -1:
            t0 = time.perf_counter_ns()
            tick += 1
            sim_time_us = tick * dt_us
            sim_time_sec = sim_time_us / 1_000_000.0
            sim_clock_s = sim_time_sec  # Drive HSR dwell timer strictly from simulation clock

            # Host OS scheduling jitter measurement (wall-clock interval between iterations)
            if last_tick_wall_ns is not None:
                interval_ms = (t0 - last_tick_wall_ns) / 1_000_000.0
                wall_intervals_ms.append(interval_ms)
                if interval_ms >= 100.0:
                    print(f"[{sim_time_sec:6.2f}s][HOST JITTER WARNING] Inter-iteration gap: {interval_ms:.1f} ms "
                          f"(approaching {params.t_watch_us / 1000:.0f} ms watchdog threshold)")
            last_tick_wall_ns = t0

            # Master clock drift invariant check
            try:
                clock_time_us = int(round(robot.getTime() * 1_000_000))
                if abs(sim_time_us - clock_time_us) > dt_us:
                    sim_time_us = state.last_tick_us if state.last_tick_us is not None else 0
            except Exception:
                pass

            # Dynamic obstacle: moves into lane at t = 3.5s
            if obstacle_trans is not None and sim_time_sec >= OBSTACLE_AT_S and not obstacle_injected:
                obstacle_injected = True
                obstacle_trans.setSFVec3f(OBSTACLE_POS)
                print(f"[{sim_time_sec:6.2f}s][HAZARD] Obstacle cart moved into lane at {OBSTACLE_POS}")

            # Read wheel position telemetry
            pos_left = left_sensor.getValue() if left_sensor else 0.0
            pos_right = right_sensor.getValue() if right_sensor else 0.0
            if prev_pos_left is None:
                prev_pos_left = pos_left
                prev_pos_right = pos_right
                meas_left_rad_s = 0.0
                meas_right_rad_s = 0.0
            else:
                meas_left_rad_s = (pos_left - prev_pos_left) / dt_s
                meas_right_rad_s = (pos_right - prev_pos_right) / dt_s
                prev_pos_left = pos_left
                prev_pos_right = pos_right

            # Drain incoming speed proposals
            proposal, _ = drain_proposals(prop_sock)

            # Operator Reset
            current_key_r_down = False
            k = keyboard.getKey()
            while k != -1:
                if (k & 0xFFFF) in (ord("R"), ord("r")):
                    current_key_r_down = True
                k = keyboard.getKey()

            r_pressed_edge = current_key_r_down and not prev_key_r_down
            prev_key_r_down = current_key_r_down

            udp_reset = poll_operator_reset(op_sock)
            reset_source = RESET_SOURCE_OPERATOR if (r_pressed_edge or udp_reset == RESET_SOURCE_OPERATOR) else None
            if reset_source is None and auto_reset_at_us is not None and not auto_reset_done \
                    and sim_time_us >= auto_reset_at_us:
                reset_source = RESET_SOURCE_OPERATOR
            if reset_source is None and auto_reset2_at_us is not None and not auto_reset2_done \
                    and sim_time_us >= auto_reset2_at_us:
                reset_source = RESET_SOURCE_OPERATOR
                auto_reset2_done = True  # one-shot
            injected3 = False
            if reset_source is None and auto_reset3_at_us is not None and not auto_reset3_done \
                    and sim_time_us >= auto_reset3_next_us:
                reset_source = RESET_SOURCE_OPERATOR
                injected3 = True  # retried every period until RESET_ACCEPTED
                auto_reset3_next_us = sim_time_us + auto_reset3_period_us

            # Simulated lidar fault
            lidar_stalled = False
            raw_ranges = lidar.getRangeImage()
            if LIDAR_FAULT in ("freeze", "stale") and sim_time_sec >= LIDAR_FAULT_SIM_S:
                if not lidar_fault_triggered:
                    lidar_fault_triggered = True
                    print(f"[{sim_time_sec:6.2f}s][LIDAR FAULT] Lidar acquisition stalled (simulating hardware freeze).")
                lidar_stalled = True
            elif LIDAR_FAULT == "blind" and sim_time_sec >= LIDAR_FAULT_SIM_S:
                if not lidar_fault_triggered:
                    lidar_fault_triggered = True
                    print(f"[{sim_time_sec:6.2f}s][LIDAR FAULT] Lidar completely blinded (simulating taped/disconnected sensor: all +inf).")
                raw_ranges = [float("inf")] * resolution
            scan, lidar_stamp_us, raw_valid_points = lidar_pipeline.process(
                raw_ranges, sim_time_us, stalled=lidar_stalled
            )

            # 4. QERRA-HSR Telemetry Evaluation
            hsr_distress = 0.0
            hsr_hazard = False
            hsr_event_active = (
                sim_time_sec >= HSR_EVENT_SIM_S
                and (HSR_EVENT_END_SIM_S is None or sim_time_sec < HSR_EVENT_END_SIM_S)
            )
            if HSR_EVENT == "distress" and hsr_event_active:
                hsr_distress = 0.85  # Breaches CRITICAL threshold (0.75)
            elif HSR_EVENT == "hazard" and hsr_event_active:
                hsr_hazard = True

            hsr_input = HSRInput(
                distress_confidence=hsr_distress,
                persons_nearby_count=0,
                hazard_proximity_flag=hsr_hazard,
                robot_task_interruptible=True,
            )
            hsr_res = hsr_companion.evaluate(hsr_input)
            hsr_status_str = hsr_res.status.value
            if hsr_status_str != last_hsr_status:
                print(f"[{sim_time_sec:6.3f}s][HSR] status {last_hsr_status} -> {hsr_status_str}")
                last_hsr_status = hsr_status_str

            inputs = GateInputs(
                sim_time_us=sim_time_us,
                proposal=proposal,
                ranges_m=scan,
                lidar_stamp_us=lidar_stamp_us,
                reset_source=reset_source,
                log_write_failed=log_failed_prev,
                raw_valid_points=raw_valid_points,
                hsr_status=hsr_status_str,
                hsr_stamp_us=sim_time_us,
            )
            log_failed_prev = False

            # Pure safety gate decision step
            res = step(state, params, inputs)
            state = res.state
            if res.reason == Reason.RESET_ACCEPTED:
                auto_reset_done = True
                if injected3:
                    auto_reset3_done = True

            # Evidence: operator reset requests and the gate's answer
            if reset_source is not None:
                _events = res.record.get("events")
                _key = (str(res.reason), str(_events))
                if _key != last_reset_print:
                    print(f"[{sim_time_sec:6.3f}s][GATE] Operator reset request -> reason={res.reason} "
                          f"events={_events} (mode: {state.mode.value})")
                    last_reset_print = _key

            # Actuator enforcement (fail-closed guarded)
            cmd_l = res.cmd_left_urad_s / 1_000_000.0
            cmd_r = res.cmd_right_urad_s / 1_000_000.0
            try:
                left_motor.setVelocity(cmd_l)
                right_motor.setVelocity(cmd_r)
            except Exception as exc:
                zero_wheels(left_motor, right_motor)
                sys.stderr.write(f"[ACTUATOR FAULT] setVelocity exception: {exc}\n")
                raise

            compute_ns.append(time.perf_counter_ns() - t0)

            # Write diagnostic telemetry CSV
            lidar_val = res.record["lidar_min_mm"] if res.record["lidar_min_mm"] is not None else ""
            telemetry_file.write(f"{sim_time_sec:.3f},{cmd_l:.3f},{cmd_r:.3f},{meas_left_rad_s:.3f},{meas_right_rad_s:.3f},{lidar_val}\n")

            # Echo master simulation time to untrusted proposer
            send_state(state_sock, sim_time_us, port=DEFAULT_STATE_PORT)

            # Console reporting
            if state.mode != last_mode or (state.mode == Mode.TRIPPED and res.reason != last_reason
                                           and res.reason.startswith("TRIP_")):
                rec = res.record
                if last_mode == Mode.RUN and state.mode == Mode.TRIPPED:
                    print("\n" + "!" * 70)
                    print(f"[{sim_time_sec:6.2f}s][GATE INTERVENTION] RUN -> TRIPPED | Reason: {res.reason}")
                    print(f"  • Lidar Min Distance : {rec['lidar_min_mm']} mm | Stop Distance: {rec['d_stop_mm']} mm")
                    print(f"  • HSR Reflex Status  : {rec['hsr_status']}")
                    print(f"  • Proposal Age       : {rec['proposal_age_us']} µs")
                    print(f"  • Command Output     : L={cmd_l:.3f} R={cmd_r:.3f} rad/s (fail-closed requires 0.000)")
                    print("!" * 70 + "\n")
                else:
                    print(f"[{sim_time_sec:6.2f}s][GATE] {last_mode.value if last_mode else 'START'} -> {state.mode.value} | Reason: {res.reason}")
                if state.mode == Mode.AWAITING_RESET:
                    print(f"[{sim_time_sec:6.2f}s][GATE] Calmed. Click 3D view and press R to reset.")
                last_mode, last_reason = state.mode, res.reason
            elif state.mode == Mode.RUN and tick % 30 == 0:
                print(f"[{sim_time_sec:6.2f}s][GATE] RUN | Cmd: {cmd_l:.2f} rad/s | Meas: L={meas_left_rad_s:.2f}, R={meas_right_rad_s:.2f} rad/s | Lidar: {res.record['lidar_min_mm']} mm | HSR: {res.record.get('hsr_status', 'CLEAR')}")

            if proposer_proc is not None and not proposer_warned and tick % 30 == 0 \
                    and proposer_proc.poll() is not None:
                proposer_warned = True
                print(f"[{sim_time_sec:6.2f}s][GATE] Proposer process exited (code {proposer_proc.returncode}). Gate holding fail-closed.")

            # Append to Flight Recorder
            try:
                logger.append(res.record, wall_ns=t0)
            except Exception as exc:
                log_failed_prev = True
                zero_wheels(left_motor, right_motor)
                print(f"[{sim_time_sec:6.2f}s][GATE] LOG WRITE FAILED ({exc!r}); tripping.")

            # Harness end-of-run
            if end_at_us is not None and sim_time_us >= end_at_us:
                print(f"[{sim_time_sec:6.2f}s][GATE] QERRA_END_AT_S reached; ending run and closing the audit log.")
                break

    except Exception:
        zero_wheels(left_motor, right_motor)
        raise
    finally:
        zero_wheels(left_motor, right_motor)
        telemetry_file.close()
        if proposer_proc is not None and proposer_proc.poll() is None:
            proposer_proc.terminate()
            try:
                proposer_proc.wait(timeout=1.0)
            except Exception:
                proposer_proc.kill()
        try:
            logger.close()
        except Exception:
            pass
        for s in (prop_sock, op_sock, state_sock):
            try:
                s.close()
            except Exception:
                pass
        if compute_ns:
            vals = sorted(compute_ns)
            try:
                with open(os.path.join(run_dir, "gate_compute_ns.txt"), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write("\n".join(str(v) for v in compute_ns) + "\n")
            except OSError:
                pass
            print(f"[GATE] Per-tick compute latency (N={len(vals)}): "
                  f"p50={percentile(vals, 0.50) / 1e3:.1f} µs | p99={percentile(vals, 0.99) / 1e3:.1f} µs | max={vals[-1] / 1e3:.1f} µs")
        if wall_intervals_ms:
            sorted_wall = sorted(wall_intervals_ms)
            print(f"[GATE HOST TIMING] Iteration wall intervals (N={len(sorted_wall)}): "
                  f"p50={percentile(sorted_wall, 0.50):.1f} ms | p99={percentile(sorted_wall, 0.99):.1f} ms | max={sorted_wall[-1]:.1f} ms")
        print(f"[GATE] Audit log closed: {log_path}")
        print(f"[GATE] Wheel telemetry closed: {telemetry_path}")


if __name__ == "__main__":
    main()
