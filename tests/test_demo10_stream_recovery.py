# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA-v2 Classical -- Demo 10 Offline Stream Recovery & Timeline Verification.
Validates the complete asynchronous frozen-frame fault, reset rejection,
dual-gate rebase dwell, and controlled recovery lifecycle using simulated time.

Standard library + gate modules only. Zero Webots or ROS 2 dependencies.
"""
from __future__ import annotations

import json
import socket
from typing import Optional

from gate.gate_config import get_live_gate_params
from gate.gate_core import (
    GateInputs,
    Mode,
    Proposal,
    Reason,
    RESET_SOURCE_OPERATOR,
    initial_state,
    step,
)
from gate.hsr_receiver import HsrReceiver


def _make_payload(
    obs_id: int,
    t_obs_us: int,
    distress_permille: int = 0,
    state: str = "CLEAR",
) -> bytes:
    """Builds a valid HSR telemetry datagram."""
    return json.dumps({
        "obs_id": obs_id,
        "t_obs_us": t_obs_us,
        "t_emit_us": t_obs_us + 1_000,
        "distress_permille": distress_permille,
        "state": state,
        "hazard_proximity": False,
        "persons_nearby_count": 2,
    }).encode("utf-8")


def test_demo10_frozen_frame_lifecycle():
    """
    Simulates the exact 14-second Demo 10 Webots timeline with 32 ms ticks:
      - 0.0s to 1.2s: Nominal startup. Reset accepted at 1.2s -> RUN.
      - 1.2s to 4.0s: Nominal cruising down corridor.
      - 4.0s to 7.0s: Frozen frame injected -> TRIP_HSR_INVALID.
      - 5.0s: Reset rejected during active freeze.
      - 7.0s: Clean frames resume -> 5-tick + 160ms rebase dwell.
      - 8.2s: Gate calm dwell complete -> Recovery reset accepted.
      - 8.2s+: Motion resumes smoothly.
    """
    dt_us = 32_000
    params = get_live_gate_params(
        lidar_n_expected=682,
        dt_us=dt_us,
        w_max_urad_s=3_000_000,
        t_react_us=32_000,
        hsr_required=True,
    )
    state = initial_state()

    # Ephemeral UDP loopback pair
    rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx_sock.setblocking(False)
    rx_sock.bind(("127.0.0.1", 0))
    port = rx_sock.getsockname()[1]

    tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = ("127.0.0.1", port)

    receiver = HsrReceiver(port=port, enabled=True, sock=rx_sock)

    obs_id = 1
    nominal_ranges = [5.0] * 682  # Obstacle-free corridor

    reset_refusal_tested = False
    recovery_reset_accepted = False
    motion_resumed = False

    try:
        # Run 438 ticks = ~14.0 seconds at 32 ms/tick
        for tick in range(1, 439):
            sim_time_us = tick * dt_us
            sim_time_s = sim_time_us / 1_000_000.0

            # Fresh untrusted proposal generated on every control tick
            proposal = Proposal(
                seq=tick,
                sim_stamp_us=sim_time_us,
                left_urad_s=2_000_000,
                right_urad_s=2_000_000,
                session_id=1,
            )

            # 1. Producer behavior simulation
            in_fault = (4.0 <= sim_time_s < 7.0)

            if in_fault:
                # FROZEN FRAME: obs_id does not advance; timestamp advances
                active_obs_id = 125
            else:
                obs_id += 1
                active_obs_id = obs_id

            # Emit packet
            payload = _make_payload(
                obs_id=active_obs_id,
                t_obs_us=sim_time_us,
                distress_permille=0,
                state="CLEAR",
            )
            tx_sock.sendto(payload, dest)

            # 2. Receiver ingestion
            hsr_status, hsr_stamp = receiver.poll(now_us=sim_time_us)

            # 3. Automated operator reset schedule
            reset_source: Optional[str] = None

            # Startup reset at 1.2s
            if 1_200_000 <= sim_time_us < 1_200_000 + dt_us:
                reset_source = RESET_SOURCE_OPERATOR

            # Mid-fault reset test at 5.0s (must be rejected)
            if 5_000_000 <= sim_time_us < 5_000_000 + dt_us:
                reset_source = RESET_SOURCE_OPERATOR

            # Post-dwell recovery reset at 8.2s (must be accepted)
            if sim_time_us >= 8_200_000 and not recovery_reset_accepted:
                reset_source = RESET_SOURCE_OPERATOR

            # 4. Gate Step
            inputs = GateInputs(
                sim_time_us=sim_time_us,
                proposal=proposal,
                ranges_m=nominal_ranges,
                lidar_stamp_us=sim_time_us,
                reset_source=reset_source,
                log_write_failed=False,
                raw_valid_points=682,
                hsr_status=hsr_status,
                hsr_stamp_us=hsr_stamp,
            )
            res = step(state, params, inputs)
            state = res.state

            # 5. Timeline Assertions

            # A. Cruising before fault (e.g. at t = 3.0s)
            if 2.0 <= sim_time_s < 4.0:
                assert state.mode == Mode.RUN, f"Expected RUN at {sim_time_s}s, got {state.mode} (reason: {res.reason})"
                assert res.cmd_left_urad_s == 2_000_000, "Left wheel must be commanding cruise velocity"
                assert res.cmd_right_urad_s == 2_000_000, "Right wheel must be commanding cruise velocity"

            # B. Gate trips immediately on frozen frame (at t = 4.032s)
            if 4.05 <= sim_time_s < 5.0:
                assert receiver.frozen_latched is True, "Receiver must latch frozen frame"
                assert hsr_status is None, "Receiver must output None status during freeze"
                assert state.mode == Mode.TRIPPED, f"Gate must be TRIPPED during freeze at {sim_time_s}s"
                assert res.reason == Reason.TRIP_HSR_INVALID, f"Expected TRIP_HSR_INVALID, got {res.reason}"
                assert res.cmd_left_urad_s == 0, "Left wheel must be clamped to 0"
                assert res.cmd_right_urad_s == 0, "Right wheel must be clamped to 0"

            # C. Reset attempted at 5.0s during fault MUST be rejected fail-closed
            if 5_000_000 <= sim_time_us < 5_000_000 + dt_us:
                assert res.reason != Reason.RESET_ACCEPTED, "Reset must not be accepted during active freeze"
                assert state.mode == Mode.TRIPPED, "Gate must remain TRIPPED when reset is rejected"
                assert res.reason == Reason.TRIP_HSR_INVALID, f"Trip reason must remain TRIP_HSR_INVALID, got {res.reason}"
                reset_refusal_tested = True

            # D. Dwell enforcement after fault ends at 7.0s
            if 7.0 < sim_time_s < 7.15:
                # Still in rebase streak dwell: receiver should still output None
                assert receiver.rebase_streak > 0, "Rebase streak must be accumulating"

            # E. Recovery reset acceptance at 8.2s
            if res.reason == Reason.RESET_ACCEPTED and sim_time_s >= 8.0:
                recovery_reset_accepted = True
                # Gate invariant: wheel commands on accepted-reset tick must be strictly 0
                assert res.cmd_left_urad_s == 0, "Accepted reset tick must remain stationary"
                assert res.cmd_right_urad_s == 0, "Accepted reset tick must remain stationary"

            # F. Movement resumed after recovery
            if recovery_reset_accepted and sim_time_s >= 8.5:
                assert state.mode == Mode.RUN, f"Expected RUN after recovery at {sim_time_s}s, got {state.mode}"
                assert res.cmd_left_urad_s == 2_000_000, "Cruise velocity must resume"
                motion_resumed = True

        # Final verification that all critical lifecycle events fired
        assert reset_refusal_tested, "Automated reset refusal at 5.0s was not exercised"
        assert recovery_reset_accepted, "Recovery reset at 8.2s was not accepted"
        assert motion_resumed, "Motion was not resumed after recovery"

    finally:
        receiver.close()
        rx_sock.close()
        tx_sock.close()
