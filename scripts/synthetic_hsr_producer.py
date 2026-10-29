# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- Synthetic Asynchronous HSR Telemetry Producer.
Phase 2 / Workstream 1: Zero-cost perception stress-testing.

Runs as an independent OS process transmitting HSRTelemetryPacket datagrams
to the Gate on UDP port 5008. Synchronizes simulation time via port 5007.

STRESS MODES:
  nominal         Continuous CLEAR readings (distress_permille = 0)
  distress_spike  Injects acute distress (850 permille, CRITICAL) for a set duration
  frozen_frame    Simulates stuck camera buffer (timestamps advance, obs_id frozen)
  burst_flood     Emits CLEAR -> CRITICAL -> CLEAR in a single tick (tests drain reduction)
  stale_hang      Halts transmission for --hang-ms (tests TRIP_HSR_STALE watchdog)

Standard library only (plus gate/ modules).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gate.gate_ipc import DEFAULT_HSR_PORT  # noqa: E402
from gate.gate_link import DEFAULT_STATE_PORT, create_state_receiver, drain_state  # noqa: E402
from gate.hsr_telemetry import (  # noqa: E402
    classify_hsr_telemetry,
    parse_hsr_telemetry,
)

DEFAULT_PERIOD_SEC = 0.032  # 32 ms (~31 Hz camera frame rate)


def build_payload(
    obs_id: int,
    sim_time_us: int,
    distress_permille: int,
    hazard_proximity: bool = False,
    persons_nearby_count: int = 2,
    inference_delay_us: int = 1_000,
) -> bytes:
    """Builds and serializes a validated HSR wire payload."""
    t_obs = sim_time_us
    t_emit = sim_time_us + inference_delay_us
    state = classify_hsr_telemetry(
        distress_permille=distress_permille,
        hazard_proximity=hazard_proximity,
        persons_nearby_count=persons_nearby_count,
    )
    packet_dict = {
        "obs_id": obs_id,
        "t_obs_us": t_obs,
        "t_emit_us": t_emit,
        "distress_permille": distress_permille,
        "state": state,
        "hazard_proximity": hazard_proximity,
        "persons_nearby_count": persons_nearby_count,
    }
    return json.dumps(packet_dict).encode("utf-8")


def run_producer(
    gate_port: int = DEFAULT_HSR_PORT,
    state_port: int = DEFAULT_STATE_PORT,
    period_sec: float = DEFAULT_PERIOD_SEC,
    mode: str = "nominal",
    event_sim_s: float = 4.0,
    event_end_sim_s: float = 7.0,
    hang_ms: int = 800,
    orphan_timeout_s: float = 15.0,
    startup_grace_s: float = 120.0,
) -> int:
    try:
        state_sock = create_state_receiver(state_port)
    except OSError as exc:
        print(f"[HSR PRODUCER] Cannot bind state port {state_port}: {exc}. "
              f"Another producer may still be running.", flush=True)
        return 2

    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    gate_addr = ("127.0.0.1", gate_port)

    obs_id = 0
    latest_sim_us = None
    hang_until_us = None
    wall_started = time.monotonic()
    wall_last_state = None

    print(f"[HSR PRODUCER] Started. gate=127.0.0.1:{gate_port} "
          f"state-in=127.0.0.1:{state_port} mode={mode}", flush=True)

    try:
        while True:
            newest, drained = drain_state(state_sock)
            now_wall = time.monotonic()
            if drained:
                wall_last_state = now_wall
            if newest is not None and (latest_sim_us is None or newest > latest_sim_us):
                latest_sim_us = newest

            # Orphan safety
            if wall_last_state is None and now_wall - wall_started > startup_grace_s:
                print("[HSR PRODUCER] No state received from Gate (startup grace expired); exiting.", flush=True)
                return 0
            if wall_last_state is not None and now_wall - wall_last_state > orphan_timeout_s:
                print(f"[HSR PRODUCER] Gate state stopped for {orphan_timeout_s:.0f}s; exiting.", flush=True)
                return 0

            if latest_sim_us is not None:
                sim_s = latest_sim_us / 1_000_000.0
                in_event = event_sim_s <= sim_s < event_end_sim_s

                # 1. Stale hang fault
                if mode == "stale_hang" and in_event and hang_until_us is None:
                    hang_until_us = latest_sim_us + hang_ms * 1_000
                    print(f"[{sim_s:6.2f}s][HSR PRODUCER] Silencing telemetry for {hang_ms} ms", flush=True)

                hanging = hang_until_us is not None and latest_sim_us < hang_until_us
                if hang_until_us is not None and not hanging:
                    print(f"[{sim_s:6.2f}s][HSR PRODUCER] Hang completed; resuming emissions", flush=True)
                    hang_until_us = None

                if not hanging:
                    # Determine active parameters
                    distress = 0
                    hazard = False
                    isolated = 2

                    if in_event and mode == "distress_spike":
                        distress = 850  # Breaches 750 CRITICAL threshold

                    # Frame counter behavior
                    active_obs_id = obs_id
                    if in_event and mode == "frozen_frame":
                        # Freeze obs_id to simulate stalled camera buffer
                        pass
                    else:
                        obs_id += 1
                        active_obs_id = obs_id

                    if mode == "burst_flood" and in_event:
                        # Emit 3 rapid packets in same tick: CLEAR, CRITICAL, CLEAR
                        p1 = build_payload(active_obs_id, latest_sim_us, 0)
                        p2 = build_payload(active_obs_id + 1, latest_sim_us + 100, 850)
                        p3 = build_payload(active_obs_id + 2, latest_sim_us + 200, 0)
                        for p in (p1, p2, p3):
                            send_sock.sendto(p, gate_addr)
                        obs_id += 2
                    else:
                        payload = build_payload(
                            obs_id=active_obs_id,
                            sim_time_us=latest_sim_us,
                            distress_permille=distress,
                            hazard_proximity=hazard,
                            persons_nearby_count=isolated,
                        )
                        send_sock.sendto(payload, gate_addr)

            time.sleep(period_sec)

    except KeyboardInterrupt:
        print("[HSR PRODUCER] Stopped by user.", flush=True)
        return 0
    finally:
        state_sock.close()
        send_sock.close()


def run_dry_run() -> int:
    """Standalone unit verification of producer payload construction and classifier alignment."""
    print("[HSR PRODUCER DRY-RUN] Testing synthetic payload generation...")

    # 1. Nominal payload
    nom_bytes = build_payload(obs_id=1, sim_time_us=32_000, distress_permille=0)
    pkt_nom = parse_hsr_telemetry(nom_bytes, t_rx_us=34_000)
    assert pkt_nom.obs_id == 1
    assert pkt_nom.state == "CLEAR"
    assert pkt_nom.severity() == 0

    # 2. Distress spike payload
    distress_bytes = build_payload(obs_id=2, sim_time_us=64_000, distress_permille=850)
    pkt_distress = parse_hsr_telemetry(distress_bytes, t_rx_us=66_000)
    assert pkt_distress.obs_id == 2
    assert pkt_distress.state == "CRITICAL"
    assert pkt_distress.severity() == 2

    # 3. Burst flood sequence validation
    burst_1 = build_payload(obs_id=3, sim_time_us=96_000, distress_permille=0)
    burst_2 = build_payload(obs_id=4, sim_time_us=96_100, distress_permille=850)
    burst_3 = build_payload(obs_id=5, sim_time_us=96_200, distress_permille=0)

    from gate.hsr_telemetry import drain_worst_severity
    batch = [
        parse_hsr_telemetry(burst_1, t_rx_us=97_000),
        parse_hsr_telemetry(burst_2, t_rx_us=97_000),
        parse_hsr_telemetry(burst_3, t_rx_us=97_000),
    ]
    winner = drain_worst_severity(batch)
    assert winner is not None
    assert winner.obs_id == 4
    assert winner.state == "CRITICAL"

    print("[HSR PRODUCER DRY-RUN] All synthetic producer checks PASSED cleanly.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic Asynchronous HSR Telemetry Producer")
    parser.add_argument("--port", type=int, default=DEFAULT_HSR_PORT, help="Gate HSR UDP port")
    parser.add_argument("--state-port", type=int, default=DEFAULT_STATE_PORT, help="Simulation time echo port")
    parser.add_argument("--period", type=float, default=DEFAULT_PERIOD_SEC, help="Send period in wall seconds")
    parser.add_argument("--mode", choices=["nominal", "distress_spike", "frozen_frame", "burst_flood", "stale_hang"],
                        default="nominal", help="Stress-test simulation mode")
    parser.add_argument("--event-sim-s", type=float, default=4.0, help="Sim time (s) when fault/event starts")
    parser.add_argument("--event-end-sim-s", type=float, default=7.0, help="Sim time (s) when fault/event ends")
    parser.add_argument("--hang-ms", type=int, default=800, help="Duration in ms to silence packets under stale_hang")
    parser.add_argument("--orphan-timeout", type=float, default=15.0, help="Exit after this many wall seconds without state")
    parser.add_argument("--dry-run", action="store_true", help="Run local self-test and exit")
    args = parser.parse_args()

    if args.dry_run:
        return run_dry_run()

    return run_producer(
        gate_port=args.port,
        state_port=args.state_port,
        period_sec=args.period,
        mode=args.mode,
        event_sim_s=args.event_sim_s,
        event_end_sim_s=args.event_end_sim_s,
        hang_ms=args.hang_ms,
        orphan_timeout_s=args.orphan_timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
