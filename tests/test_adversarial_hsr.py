# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Adversarial security and denial-of-service tests for Layer 1B UDP reflex ingestion.
Demonstrates concrete vulnerabilities identified in SAFETY_CONCEPT.md and Section 4.6:
  1. Masked-distress re-arm: An unauthenticated local attacker can forge a producer restart,
     satisfy the rebase and clear dwells, and force the Gate back into RUN after real distress.
  2. Ingestion crowding: A flood exceeding MAX_DRAIN_PER_CALL (256 datagrams) delays
     evaluation of a legitimate CRITICAL distress datagram across control ticks.
Standard library only. Executes on Windows without ROS 2.
"""
from __future__ import annotations

import json
import socket
import unittest

from gate.gate_config import get_live_gate_params
from gate.gate_core import (
    GateInputs,
    GateParams,
    Mode,
    Proposal,
    Reason,
    RESET_SOURCE_OPERATOR,
    initial_state,
    step,
)
from gate.gate_ipc import MAX_DRAIN_PER_CALL
from ros2.hsr_receiver import HsrReceiver


def _json_pkt(obs_id: int, t_obs_us: int, state: str = "CLEAR", distress: int = 0) -> bytes:
    """Helper formatting wire JSON payloads."""
    return json.dumps({
        "obs_id": obs_id,
        "t_obs_us": t_obs_us,
        "t_emit_us": t_obs_us + 1_000,
        "distress_permille": distress,
        "state": state,
    }).encode("utf-8")


def _make_nominal_proposal(sim_time_us: int) -> Proposal:
    """Constructs a forward motion proposal at 0.15 m/s."""
    return Proposal(
        seq=1,
        sim_stamp_us=sim_time_us,
        left_urad_s=1_530_612,
        right_urad_s=1_530_612,
        session_id=1,
    )


class TestAdversarialHsr(unittest.TestCase):
    """Adversarial vulnerability demonstrations (Section 4.6)."""

    def test_adversarial_masked_distress_rearm_succeeds_without_auth(self) -> None:
        """
        VULNERABILITY DEMONSTRATION (Section 4.6a):
        When the genuine perception producer is silenced, an unauthenticated local process
        can send a forged counter regression, forge 5 ticks (>= 160 ms) of advancing CLEAR
        frames, sustain CLEAR for the 1.0 s gate clear dwell, and send an operator reset.
        The Gate core returns to Mode.RUN despite genuine distress having occurred.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        attacker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dest = ("127.0.0.1", port)

        rx = HsrReceiver(port=port, enabled=True, sock=sock)
        params: GateParams = get_live_gate_params(lidar_n_expected=682, hsr_required=True)
        gate_state = initial_state()

        now_us = 1_000_000

        # Phase 1: Legitimate system trips on acute distress (CRITICAL)
        attacker.sendto(_json_pkt(obs_id=100, t_obs_us=now_us, state="CRITICAL", distress=800), dest)
        status, stamp = rx.poll(now_us)
        self.assertEqual(status, "CRITICAL")

        inputs = GateInputs(
            sim_time_us=now_us,
            proposal=_make_nominal_proposal(now_us),
            ranges_m=[2.0] * 682,
            lidar_stamp_us=now_us,
            hsr_status=status,
            hsr_stamp_us=stamp,
        )
        res = step(gate_state, params, inputs)
        gate_state = res.state
        self.assertEqual(gate_state.mode, Mode.TRIPPED)
        self.assertEqual(res.reason, Reason.TRIP_HSR_CRITICAL)

        # Phase 2: Genuine producer is silenced. Attacker begins forged restart (regression)
        now_us += 32_000
        attacker.sendto(_json_pkt(obs_id=0, t_obs_us=now_us, state="CLEAR", distress=0), dest)
        status, stamp = rx.poll(now_us)
        self.assertIsNone(status, "Receiver enters rebase dwell; status is None")
        self.assertTrue(rx.rebase_in_progress)

        # Attacker feeds 5 clean advancing ticks (i = 1..5) spaced by 40 ms each.
        # Start t_obs is latched at i=1 (now_us + 40_000).
        # At i=5, elapsed sensor time is 4 * 40_000 = 160_000 us, and streak is 5.
        for i in range(1, 6):
            now_us += 40_000
            attacker.sendto(_json_pkt(obs_id=i, t_obs_us=now_us, state="CLEAR", distress=0), dest)
            status, stamp = rx.poll(now_us)
            inputs = GateInputs(
                sim_time_us=now_us,
                proposal=_make_nominal_proposal(now_us),
                ranges_m=[2.0] * 682,
                lidar_stamp_us=now_us,
                hsr_status=status,
                hsr_stamp_us=stamp,
            )
            res = step(gate_state, params, inputs)
            gate_state = res.state

        # At tick 5, receiver rebase dwell finishes and outputs CLEAR
        self.assertFalse(rx.rebase_in_progress, "Rebase dwell must complete on 5th clean tick")
        self.assertEqual(status, "CLEAR")

        # Phase 3: Attacker maintains forged CLEAR frames for 1.0 s (32 ticks) to satisfy Gate dwell
        for i in range(6, 39):
            now_us += 32_000
            attacker.sendto(_json_pkt(obs_id=i, t_obs_us=now_us, state="CLEAR", distress=0), dest)
            status, stamp = rx.poll(now_us)
            inputs = GateInputs(
                sim_time_us=now_us,
                proposal=_make_nominal_proposal(now_us),
                ranges_m=[2.0] * 682,
                lidar_stamp_us=now_us,
                hsr_status=status,
                hsr_stamp_us=stamp,
            )
            res = step(gate_state, params, inputs)
            gate_state = res.state

        # Gate has finished clear dwell and is armed for reset
        self.assertEqual(gate_state.mode, Mode.AWAITING_RESET)

        # Phase 4: Attacker injects forged operator reset
        now_us += 32_000
        attacker.sendto(_json_pkt(obs_id=39, t_obs_us=now_us, state="CLEAR", distress=0), dest)
        status, stamp = rx.poll(now_us)
        inputs = GateInputs(
            sim_time_us=now_us,
            proposal=_make_nominal_proposal(now_us),
            ranges_m=[2.0] * 682,
            lidar_stamp_us=now_us,
            reset_source=RESET_SOURCE_OPERATOR,
            hsr_status=status,
            hsr_stamp_us=stamp,
        )
        res = step(gate_state, params, inputs)
        gate_state = res.state

        # EXPLOIT CONFIRMATION: The Gate returns to Mode.RUN under forged unauthenticated telemetry
        self.assertEqual(gate_state.mode, Mode.RUN, "Vulnerability confirmed: Gate re-arms to RUN")
        self.assertEqual(res.reason, Reason.RESET_ACCEPTED)

        rx.close()
        sock.close()
        attacker.close()

    def test_adversarial_flood_above_max_drain_delays_critical(self) -> None:
        """
        VULNERABILITY DEMONSTRATION (Section 4.6b):
        If an attacker floods more than MAX_DRAIN_PER_CALL (256) valid CLEAR datagrams
        into the UDP buffer ahead of a legitimate CRITICAL datagram, the CRITICAL datagram
        cannot be ingested on the current control cycle, delaying the protective stop.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dest = ("127.0.0.1", port)

        rx = HsrReceiver(port=port, enabled=True, sock=sock)
        now_us = 1_000_000

        # Attacker floods 260 valid CLEAR packets (exceeding MAX_DRAIN_PER_CALL = 256)
        for i in range(1, 261):
            sender.sendto(_json_pkt(obs_id=i, t_obs_us=now_us, state="CLEAR", distress=0), dest)

        # Legitimate producer sends CRITICAL datagram #261 at the end of the OS queue
        sender.sendto(_json_pkt(obs_id=261, t_obs_us=now_us, state="CRITICAL", distress=900), dest)

        # Gate tick executes: drains exactly MAX_DRAIN_PER_CALL (256) datagrams
        status, stamp = rx.poll(now_us)

        # EXPLOIT CONFIRMATION:
        # In this control cycle, the receiver drained 256 packets, seeing ONLY CLEAR.
        # The CRITICAL packet was left sitting unread in the socket buffer.
        self.assertEqual(status, "CLEAR", "Vulnerability confirmed: CRITICAL was crowded out on Tick 1")
        self.assertEqual(rx.last_obs_id, 256)

        # Next control cycle: the remaining datagrams (including CRITICAL #261) are drained
        now_us += 32_000
        status_tick2, _ = rx.poll(now_us)
        self.assertEqual(status_tick2, "CRITICAL", "CRITICAL is finally ingested on Tick 2")
        self.assertEqual(rx.last_obs_id, 261)

        rx.close()
        sock.close()
        sender.close()


if __name__ == "__main__":
    unittest.main()
