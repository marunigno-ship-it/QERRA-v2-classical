# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- Untrusted Deliberation Proposer (Demo 7), version 0.3.
SAFETY_CONCEPT.md v0.1: AR-2, AR-6, C-1, C-4.

Runs as an independent OS process. Proposes wheel speeds to the gate over localhost UDP.

WHAT CHANGED FROM 0.2
  Adds `session_id` generated from monotonic timestamp at process startup to prevent
  proposer restart lockout (F3 fix).

FAULTS (all triggered by SIM time, as echoed by the gate, not by wall time)
  hang       stop sending for --hang-ms of sim time, keep listening, then resume
  die        exit immediately (simulated crash)
  nan        send one datagram containing a NaN value, then carry on
  oversized  send one 4096-byte datagram, then carry on

LIMITS (say these out loud when you show it)
  * Live mode only. The proposer wakes every --period seconds of WALL time. That matches the
    gate's SIM ticks only when Webots runs at about 1x real time. In fast mode healthy
    proposals look late and the gate trips. Reproducible sweeps need the lockstep harness.
  * It exits by itself if the gate's state stops arriving for --orphan-timeout wall seconds,
    so a proposer left over from a killed run cannot feed the next run.
Standard library only (plus gate/gate_link.py, which is standard library only).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gate.gate_link import DEFAULT_STATE_PORT, create_state_receiver, drain_state  # noqa: E402

DEFAULT_GATE_PORT = 5005
DEFAULT_SPEED_URAD_S = 2_000_000   # 2.0 rad/s
DEFAULT_PERIOD_SEC = 0.030         # 30 ms (D-5: proposer period <= 33 ms)


def run_proposer(
    gate_port: int = DEFAULT_GATE_PORT,
    state_port: int = DEFAULT_STATE_PORT,
    target_speed: int = DEFAULT_SPEED_URAD_S,
    period_sec: float = DEFAULT_PERIOD_SEC,
    fault: str = "none",
    fault_sim_s: float = 3.0,
    hang_ms: int = 800,
    orphan_timeout_s: float = 15.0,
    startup_grace_s: float = 120.0,
) -> int:
    try:
        state_sock = create_state_receiver(state_port)
    except OSError as exc:
        print(f"[PROPOSER] cannot bind state port {state_port}: {exc}. "
              f"Another proposer from an earlier run may still be running.", flush=True)
        return 2

    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    gate_addr = ("127.0.0.1", gate_port)

    # Monotonic incarnation session ID across restarts (F3 fix)
    session_id = int(time.time() * 1000)
    seq = 0
    latest_sim_us = None
    fault_triggered = False
    hang_until_us = None
    wall_started = time.monotonic()
    wall_last_state = None

    print(f"[PROPOSER] started (session_id={session_id}). gate=127.0.0.1:{gate_port} "
          f"state-in=127.0.0.1:{state_port} speed={target_speed} urad/s", flush=True)
    if fault != "none":
        print(f"[PROPOSER] fault '{fault}' scheduled at sim t={fault_sim_s:.2f}s", flush=True)

    try:
        while True:
            newest, drained = drain_state(state_sock)
            now_wall = time.monotonic()
            if drained:
                wall_last_state = now_wall
            if newest is not None and (latest_sim_us is None or newest > latest_sim_us):
                latest_sim_us = newest

            # Orphan protection.
            if wall_last_state is None and now_wall - wall_started > startup_grace_s:
                print("[PROPOSER] no state from the gate at all; exiting.", flush=True)
                return 0
            if wall_last_state is not None and now_wall - wall_last_state > orphan_timeout_s:
                print(f"[PROPOSER] no state from the gate for {orphan_timeout_s:.0f}s; exiting.", flush=True)
                return 0

            if latest_sim_us is not None:
                # Scheduled fault, in SIM time.
                if fault != "none" and not fault_triggered and latest_sim_us >= int(fault_sim_s * 1_000_000):
                    fault_triggered = True
                    if fault == "die":
                        print(f"[PROPOSER FAULT] simulated crash at sim t={latest_sim_us / 1e6:.3f}s", flush=True)
                        return 0
                    if fault == "hang":
                        hang_until_us = latest_sim_us + hang_ms * 1000
                        print(f"[PROPOSER FAULT] hang: silent for {hang_ms} ms of sim time "
                              f"(from sim t={latest_sim_us / 1e6:.3f}s)", flush=True)
                    elif fault == "nan":
                        print("[PROPOSER FAULT] sending a NaN payload", flush=True)
                        send_sock.sendto(
                            b'{"seq": 999, "sim_stamp_us": 999999, "left_urad_s": NaN, "right_urad_s": 2000000}',
                            gate_addr)
                    elif fault == "oversized":
                        print("[PROPOSER FAULT] sending an oversized 4096-byte packet", flush=True)
                        send_sock.sendto(b"X" * 4096, gate_addr)

                hanging = hang_until_us is not None and latest_sim_us < hang_until_us
                if hang_until_us is not None and not hanging:
                    print(f"[PROPOSER] hang over at sim t={latest_sim_us / 1e6:.3f}s; resuming", flush=True)
                    hang_until_us = None

                if not hanging:
                    payload = {
                        "session_id": session_id,
                        "seq": seq,
                        "sim_stamp_us": latest_sim_us,       # echo of the gate's sim time (not wall time)
                        "left_urad_s": target_speed,
                        "right_urad_s": target_speed,
                    }
                    try:
                        send_sock.sendto(json.dumps(payload).encode("utf-8"), gate_addr)
                    except OSError:
                        pass
                    seq += 1

            time.sleep(period_sec)
    except KeyboardInterrupt:
        print("[PROPOSER] stopped by user.", flush=True)
        return 0
    finally:
        state_sock.close()
        send_sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Untrusted proposer for the QERRA supervisory gate")
    parser.add_argument("--port", type=int, default=DEFAULT_GATE_PORT, help="gate proposal port")
    parser.add_argument("--state-port", type=int, default=DEFAULT_STATE_PORT, help="port the gate sends its sim time to")
    parser.add_argument("--speed", type=int, default=DEFAULT_SPEED_URAD_S, help="wheel speed in micro-rad/s")
    parser.add_argument("--period", type=float, default=DEFAULT_PERIOD_SEC, help="send period, wall seconds")
    parser.add_argument("--fault", choices=["none", "hang", "die", "nan", "oversized"], default="none")
    parser.add_argument("--fault-sim-s", type=float, default=3.0, help="sim time (s) at which the fault fires")
    parser.add_argument("--hang-ms", type=int, default=800, help="hang length in ms of SIM time")
    parser.add_argument("--orphan-timeout", type=float, default=15.0, help="exit after this many wall s without gate state")
    args = parser.parse_args()
    return run_proposer(
        gate_port=args.port, state_port=args.state_port, target_speed=args.speed,
        period_sec=args.period, fault=args.fault, fault_sim_s=args.fault_sim_s,
        hang_ms=args.hang_ms, orphan_timeout_s=args.orphan_timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
