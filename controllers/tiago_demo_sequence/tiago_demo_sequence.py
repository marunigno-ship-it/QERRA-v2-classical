# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- Webots Demo Sequencer Controller (Demo 8), version 0.4.
Scripted fault and reset demonstration controller. Does NOT alter any gate core logic.

Demo Stages:
  1. Safe startup & clear dwell -> operator reset -> RUN
  2. Cruise towards cart obstacle -> TRIP_OBSTACLE
  3. Operator attempts reset with cart in lane -> RESET_REJECTED_HAZARD (operator R key, with 4.0s fallback)
  4. Cart moved out of lane to y = 0.8 (dynamic world coordinates)
  5. Clear dwell (1.0 s) -> operator reset -> RUN
  6. 2.0 s motion -> Hokuyo lidar freeze fault -> TRIP_SENSOR_INVALID
  7. Lidar restored -> clear dwell (1.0 s) -> operator reset -> RUN
  8. 2.0 s motion -> Proposer candidate dropped by harness -> TRIP_PROPOSER_STALE
  9. Proposer candidate stream restored -> clear dwell (1.0 s) -> operator reset -> RUN
 10. Final cruise towards obstacle in lane (pedestrian at x=3.7) -> TRIP_OBSTACLE (Safe termination)
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
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

# Webots robot import with standalone fallback
try:
    from controller import Supervisor as RobotClass
except ImportError:
    RobotClass = object

from gate.gate_config import get_live_gate_params
from gate.gate_core import (
    GATE_CORE_VERSION, GateInputs, Mode, Reason, Event, RESET_SOURCE_OPERATOR, initial_state, step,
)
from gate.gate_ipc import create_udp_receiver, drain_proposals, poll_operator_reset
from gate.gate_lidar import CorridorFilter, LidarPipeline
from gate.gate_link import DEFAULT_STATE_PORT, create_state_sender, send_state
from gate.gate_log import (
    GateLogger, capture_harness_manifest, write_run_manifest,
)

# ----------------------------------------------------------------------------------------
# PARAMETERS: TIAGo Kinematics & Ports
# ----------------------------------------------------------------------------------------
WHEEL_RADIUS_MM = 98                 # TIAGo base wheel radius (98 mm)
ROBOT_HALF_WIDTH_M = 0.27 + 0.05     # half of ~0.54 m base width + 5 cm margin = 0.32 m
W_MAX_URAD_S = 3_000_000             # 3.0 rad/s velocity envelope cap
PROPOSER_SPEED_URAD_S = 2_000_000    # 2.0 rad/s cruise speed (196 mm/s)

PROPOSAL_PORT = 5005
OPERATOR_PORT = 5006

# Sequencer States
STAGE_STARTUP = 0
STAGE_DRIVE_TO_CART = 1
STAGE_CART_STOPPED = 2
STAGE_WAIT_RESET_AFTER_CART = 3
STAGE_DRIVE_BEFORE_LIDAR_FREEZE = 4
STAGE_LIDAR_FREEZE_ACTIVE = 5
STAGE_WAIT_RESET_AFTER_LIDAR = 6
STAGE_DRIVE_BEFORE_PROPOSER_LOSS = 7
STAGE_PROPOSER_LOSS_ACTIVE = 8
STAGE_WAIT_RESET_AFTER_PROPOSER = 9
STAGE_FINAL_DRIVE_TO_WALL = 10
STAGE_DEMO_FINISHED = 11


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
    cands = []
    for i in range(robot.getNumberOfDevices()):
        dev = robot.getDeviceByIndex(i)
        low = dev.getName().lower()
        if "hokuyo" in low or "lidar" in low or "laser" in low:
            cands.append(dev)
    if not cands:
        raise RuntimeError("No lidar device found on robot. Check lidarSlot in world.")
    return cands[0]


def zero_wheels(left, right):
    try:
        left.setVelocity(0.0)
        right.setVelocity(0.0)
    except Exception:
        pass


def percentile(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    idx = min(len(sorted_vals) - 1, max(0, int(math.ceil(q * len(sorted_vals))) - 1))
    return sorted_vals[idx]


def main():
    robot = RobotClass()
    timestep = int(robot.getBasicTimeStep())
    dt_us = timestep * 1000
    dt_s = timestep / 1000.0

    # 1. Actuators & Position Sensors
    left_motor = robot.getDevice("wheel_left_joint")
    right_motor = robot.getDevice("wheel_right_joint")
    if left_motor is None or right_motor is None:
        raise RuntimeError("wheel_left_joint / wheel_right_joint not found.")
    left_motor.setPosition(float("inf"))
    right_motor.setPosition(float("inf"))
    zero_wheels(left_motor, right_motor)
    max_vel = min(left_motor.getMaxVelocity(), right_motor.getMaxVelocity())
    w_max_urad_s = min(W_MAX_URAD_S, int(max_vel * 1_000_000))

    left_sensor = left_motor.getPositionSensor()
    right_sensor = right_motor.getPositionSensor()
    if left_sensor:
        left_sensor.enable(timestep)
    if right_sensor:
        right_sensor.enable(timestep)

    # 2. Obstacle handle from simulation tree
    node = robot.getFromDef("OBSTACLE")
    obstacle_trans = node.getField("translation") if node else None

    # 3. Lidar Pipeline
    lidar = find_lidar(robot)
    lidar.enable(timestep)
    resolution = lidar.getHorizontalResolution()
    fov = lidar.getFov()
    corridor = CorridorFilter(resolution, fov, ROBOT_HALF_WIDTH_M)
    lidar_pipeline = LidarPipeline(corridor=corridor)

    # 4. Keyboard & Sockets
    keyboard = robot.getKeyboard()
    keyboard.enable(timestep)
    prop_sock = create_udp_receiver(port=PROPOSAL_PORT)
    op_sock = create_udp_receiver(port=OPERATOR_PORT)
    state_sock = create_state_sender()

    # 5. Gate Core Parameters & State
    params = get_live_gate_params(
        lidar_n_expected=resolution,
        dt_us=dt_us,
        w_max_urad_s=w_max_urad_s,
        t_react_us=32_000,
    )
    state = initial_state()

    # 6. Safety Run Directory Check (Rule 3: Refuse to overwrite existing results)
    run_id = os.environ.get("QERRA_RUN_ID") or f"DEMO8_VIDEO_{int(time.time())}"
    run_dir = os.path.join(PROJECT_ROOT, "results", run_id)
    if os.path.exists(run_dir):
        raise RuntimeError(f"Safety violation: Run folder '{run_dir}' already exists! Refusing to reuse.")
    os.makedirs(run_dir, exist_ok=False)

    manifest = capture_harness_manifest()
    manifest["run_id"] = run_id
    manifest["gate_version"] = GATE_CORE_VERSION
    manifest["params"] = asdict(params)
    manifest["code_hashes"] = get_critical_code_hashes(PROJECT_ROOT)
    manifest["demo_sequencer"] = {
        "enabled": True,
        "timings_s": {
            "auto_reset_fallback_after_cart_stop_s": 4.0,
            "motion_before_lidar_freeze_s": 2.0,
            "lidar_freeze_duration_s": 1.0,
            "motion_before_proposer_loss_s": 2.0,
            "proposer_loss_duration_s": 1.0,
            "dwell_s": 1.0,
        },
        "injected_auto_reset_fallback": True,
        "proposer_loss_mechanism": "controller_candidate_drop",
        "schedule": [
            "STAGE_STARTUP",
            "STAGE_DRIVE_TO_CART",
            "STAGE_CART_STOPPED",
            "STAGE_WAIT_RESET_AFTER_CART",
            "STAGE_DRIVE_BEFORE_LIDAR_FREEZE",
            "STAGE_LIDAR_FREEZE_ACTIVE",
            "STAGE_WAIT_RESET_AFTER_LIDAR",
            "STAGE_DRIVE_BEFORE_PROPOSER_LOSS",
            "STAGE_PROPOSER_LOSS_ACTIVE",
            "STAGE_WAIT_RESET_AFTER_PROPOSER",
            "STAGE_FINAL_DRIVE_TO_WALL",
            "STAGE_DEMO_FINISHED",
        ],
    }
    write_run_manifest(run_dir, manifest)

    log_path = os.path.join(run_dir, "gate_audit.jsonl")
    telemetry_path = os.path.join(run_dir, "wheel_telemetry.csv")
    logger = GateLogger(log_path, run_id=run_id, gate_version=GATE_CORE_VERSION, manifest=manifest)
    telemetry_file = open(telemetry_path, "w", encoding="utf-8", newline="\n")
    telemetry_file.write("sim_time_sec,cmd_left_rad_s,cmd_right_rad_s,meas_left_rad_s,meas_right_rad_s,lidar_min_mm\n")

    # 7. Untrusted Proposer Process (Elevated priority on Windows to prevent OS scheduling starvation)
    proposer_proc = None
    proposer_script = os.path.join(PROJECT_ROOT, "scripts", "untrusted_proposer.py")
    if os.path.isfile(proposer_script):
        cmd = [
            sys.executable, "-u", proposer_script,
            "--port", str(PROPOSAL_PORT), "--state-port", str(DEFAULT_STATE_PORT),
            "--speed", str(PROPOSER_SPEED_URAD_S),
            "--fault", "none",
        ]
        cflags = subprocess.ABOVE_NORMAL_PRIORITY_CLASS if sys.platform == "win32" else 0
        proposer_proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, creationflags=cflags)

    print("\n" + "=" * 70)
    print(f"QERRA Supervisory Gate v{GATE_CORE_VERSION} -- DEMO 8 SEQUENCER")
    print(f"  • Run ID         : {run_id}")
    print(f"  • Status         : Initializing fail-closed safety gate...")
    print("=" * 70 + "\n")

    tick = 0
    stage = STAGE_STARTUP
    stage_motion_start_sec = 0.0
    fault_start_sec = 0.0
    cart_stop_time = 0.0
    prompted_ready = False

    lidar_stalled = False
    drop_proposals = False

    last_mode, last_reason = None, None
    prev_pos_left, prev_pos_right = None, None
    prev_key_r_down = False
    compute_ns = []

    try:
        while robot.step(timestep) != -1:
            tick += 1
            sim_time_us = tick * dt_us
            sim_time_sec = sim_time_us / 1_000_000.0
            t0 = time.perf_counter_ns()

            # Master sim time drift invariant
            try:
                clock_time_us = int(round(robot.getTime() * 1_000_000))
                if abs(sim_time_us - clock_time_us) > dt_us:
                    sim_time_us = state.last_tick_us if state.last_tick_us is not None else 0
            except Exception:
                pass

            # Read wheel position telemetry
            pos_left = left_sensor.getValue() if left_sensor else 0.0
            pos_right = right_sensor.getValue() if right_sensor else 0.0
            if prev_pos_left is None:
                prev_pos_left, prev_pos_right = pos_left, pos_right
                meas_left_rad_s, meas_right_rad_s = 0.0, 0.0
            else:
                meas_left_rad_s = (pos_left - prev_pos_left) / dt_s
                meas_right_rad_s = (pos_right - prev_pos_right) / dt_s
                prev_pos_left, prev_pos_right = pos_left, pos_right

            # Untrusted Proposal Ingestion (Socket always drained)
            proposal, _ = drain_proposals(prop_sock)
            if drop_proposals:
                proposal = None  # Inject proposer loss by dropping candidate

            # Operator Reset Input (R Key Edge)
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

            # Automatic fallback for obstacle reset test if user does not press R within 4s
            if stage == STAGE_CART_STOPPED and (sim_time_sec - cart_stop_time >= 4.0) and reset_source is None:
                reset_source = RESET_SOURCE_OPERATOR

            # Lidar Sensor Processing
            raw_ranges = lidar.getRangeImage()
            scan, lidar_stamp_us, raw_valid_points = lidar_pipeline.process(
                raw_ranges, sim_time_us, stalled=lidar_stalled
            )

            inputs = GateInputs(
                sim_time_us=sim_time_us,
                proposal=proposal,
                ranges_m=scan,
                lidar_stamp_us=lidar_stamp_us,
                reset_source=reset_source,
                log_write_failed=False,
                raw_valid_points=raw_valid_points,
            )

            # Pure Safety Gate Decision Step
            res = step(state, params, inputs)
            state = res.state

            # Wheel Actuator Enforcement
            cmd_l = res.cmd_left_urad_s / 1_000_000.0
            cmd_r = res.cmd_right_urad_s / 1_000_000.0
            left_motor.setVelocity(cmd_l)
            right_motor.setVelocity(cmd_r)
            compute_ns.append(time.perf_counter_ns() - t0)

            # Record Telemetry
            lidar_val = res.record["lidar_min_mm"] if res.record["lidar_min_mm"] is not None else ""
            telemetry_file.write(f"{sim_time_sec:.3f},{cmd_l:.3f},{cmd_r:.3f},{meas_left_rad_s:.3f},{meas_right_rad_s:.3f},{lidar_val}\n")
            send_state(state_sock, sim_time_us, port=DEFAULT_STATE_PORT)

            # Console Reporting (Gate Mode & Reason)
            if state.mode != last_mode or (state.mode == Mode.TRIPPED and res.reason != last_reason and res.reason.startswith("TRIP_")):
                rec = res.record
                if last_mode == Mode.RUN and state.mode == Mode.TRIPPED:
                    print("\n" + "!" * 70)
                    print(f"[{sim_time_sec:6.2f}s][GATE INTERVENTION] RUN -> TRIPPED | Reason: {res.reason}")
                    print(f"  • Lidar Min Distance : {rec['lidar_min_mm']} mm | Stop Distance: {rec['d_stop_mm']} mm")
                    print(f"  • Command Output     : 0.0 rad/s (FAIL-CLOSED)")
                    print("!" * 70 + "\n")
                else:
                    print(f"[{sim_time_sec:6.2f}s][GATE] {last_mode.value if last_mode else 'START'} -> {state.mode.value} | Reason: {res.reason}")
                last_mode, last_reason = state.mode, res.reason

            # Prompt Operator when Gate is Ready for Reset
            if state.mode == Mode.AWAITING_RESET and not prompted_ready:
                print(f"[{sim_time_sec:6.2f}s] >>> READY: press R now <<<")
                prompted_ready = True
            elif state.mode != Mode.AWAITING_RESET:
                prompted_ready = False

            # --------------------------------------------------------------------
            # Demo 8 Event Sequencer State Machine
            # --------------------------------------------------------------------
            if stage == STAGE_STARTUP:
                if res.reason == Reason.RESET_ACCEPTED:
                    stage = STAGE_DRIVE_TO_CART
                    print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 1: Reset accepted. Driving towards obstacle...")

            elif stage == STAGE_DRIVE_TO_CART:
                if state.mode == Mode.TRIPPED and res.reason == Reason.TRIP_OBSTACLE:
                    stage = STAGE_CART_STOPPED
                    cart_stop_time = sim_time_sec
                    print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 2: Stopped at obstacle. Press R within 4.0s to test reset refusal:")

            elif stage == STAGE_CART_STOPPED:
                # Triggered when reset is attempted while cart is in lane
                if reset_source is not None:
                    if Event.RESET_REJECTED_HAZARD in res.events:
                        print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 3: reset refused: RESET_REJECTED_HAZARD")
                    else:
                        print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 3: no reset refusal recorded")
                    if obstacle_trans is not None:
                        pos = obstacle_trans.getSFVec3f()
                        # Move cart aside using real world coordinates without hardcoding X or Z
                        obstacle_trans.setSFVec3f([pos[0], 0.8, pos[2]])
                        print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 4: Cart moved aside to y=0.8 (x={pos[0]:.2f}, z={pos[2]:.2f}). Corridor clear.")
                    stage = STAGE_WAIT_RESET_AFTER_CART

            elif stage == STAGE_WAIT_RESET_AFTER_CART:
                if res.reason == Reason.RESET_ACCEPTED:
                    stage = STAGE_DRIVE_BEFORE_LIDAR_FREEZE
                    stage_motion_start_sec = sim_time_sec
                    print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 5: Reset accepted. Cruising before sensor fault...")

            elif stage == STAGE_DRIVE_BEFORE_LIDAR_FREEZE:
                if (sim_time_sec - stage_motion_start_sec) >= 2.0:
                    stage = STAGE_LIDAR_FREEZE_ACTIVE
                    fault_start_sec = sim_time_sec
                    lidar_stalled = True
                    print(f"[{sim_time_sec:6.2f}s][DEMO FAULT] Stage 6: Injecting Lidar Freeze (simulating sensor lockup)...")

            elif stage == STAGE_LIDAR_FREEZE_ACTIVE:
                lidar_stalled = True
                if (sim_time_sec - fault_start_sec) >= 1.0:
                    lidar_stalled = False
                    stage = STAGE_WAIT_RESET_AFTER_LIDAR
                    print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 7: Lidar restored. Waiting 1.0s safety dwell...")

            elif stage == STAGE_WAIT_RESET_AFTER_LIDAR:
                if res.reason == Reason.RESET_ACCEPTED:
                    stage = STAGE_DRIVE_BEFORE_PROPOSER_LOSS
                    stage_motion_start_sec = sim_time_sec
                    print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 8: Reset accepted. Cruising before proposer fault...")

            elif stage == STAGE_DRIVE_BEFORE_PROPOSER_LOSS:
                if (sim_time_sec - stage_motion_start_sec) >= 2.0:
                    stage = STAGE_PROPOSER_LOSS_ACTIVE
                    fault_start_sec = sim_time_sec
                    drop_proposals = True
                    print(f"[{sim_time_sec:6.2f}s][DEMO FAULT] Stage 9: Injecting Proposer Loss (simulating proposal dropout)...")

            elif stage == STAGE_PROPOSER_LOSS_ACTIVE:
                drop_proposals = True
                if (sim_time_sec - fault_start_sec) >= 1.0:
                    drop_proposals = False
                    stage = STAGE_WAIT_RESET_AFTER_PROPOSER
                    print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 10: Proposer stream restored. Waiting 1.0s safety dwell...")

            elif stage == STAGE_WAIT_RESET_AFTER_PROPOSER:
                if res.reason == Reason.RESET_ACCEPTED:
                    stage = STAGE_FINAL_DRIVE_TO_WALL
                    print(f"[{sim_time_sec:6.2f}s][DEMO] Stage 11: Final drive: proceeding toward obstacle ahead...")

            elif stage == STAGE_FINAL_DRIVE_TO_WALL:
                if state.mode == Mode.TRIPPED and res.reason == Reason.TRIP_OBSTACLE:
                    stage = STAGE_DEMO_FINISHED
                    lidar_min_str = str(res.record.get("lidar_min_mm"))
                    stop_mm_str = str(res.record.get("d_stop_mm"))
                    print("\n" + "=" * 70)
                    print(f"[{sim_time_sec:6.2f}s][DEMO COMPLETE] Sequence ended. Final stop: obstacle ahead at {lidar_min_str} mm. See the log.")
                    print(f"  • Reason         : {res.reason}")
                    print(f"  • Mode           : {state.mode.value}")
                    print(f"  • Lidar Min Range: {lidar_min_str} mm | Stopping Envelope: {stop_mm_str} mm")
                    print("Stop Webots simulation.")
                    print("=" * 70 + "\n")

            # Periodic Status Log during RUN
            if state.mode == Mode.RUN and tick % 30 == 0:
                print(f"[{sim_time_sec:6.2f}s][GATE] RUN | Cmd: {cmd_l:.2f} rad/s | Meas: L={meas_left_rad_s:.2f}, R={meas_right_rad_s:.2f} rad/s | Lidar: {res.record['lidar_min_mm']} mm")

            # Append to Flight Recorder
            logger.append(res.record, wall_ns=t0)

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
        print(f"[GATE] Audit log closed for run: {run_id}")
        print(f"[GATE] Wheel telemetry closed for run: {run_id}")


if __name__ == "__main__":
    main()
