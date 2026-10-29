# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
End-to-end integration test for QERRA Phase 2 Asynchronous HSR Telemetry.
Wires synthetic producer payloads across live localhost UDP sockets into
gate_ipc.drain_hsr_telemetry() and gate_core.step().
Standard library only. Zero Webots dependency.
"""
from __future__ import annotations

import socket
import unittest

from gate.gate_core import (
    GateInputs,
    GateParams,
    Mode,
    Proposal,
    Reason,
    initial_state,
    step,
)
from gate.gate_ipc import (
    create_udp_receiver,
    drain_hsr_telemetry,
)
from gate.hsr_telemetry import is_perception_frozen
from scripts.synthetic_hsr_producer import build_payload


class TestAsyncHSRPipeline(unittest.TestCase):

    def setUp(self):
        # Ephemeral UDP receiver socket to eliminate Windows port collision
        self.recv_sock = create_udp_receiver(port=0)
        self.port = self.recv_sock.getsockname()[1]
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dest = ("127.0.0.1", self.port)

        # Standard test parameters requiring live HSR telemetry
        self.params = GateParams(
            lidar_n_expected=10,
            hsr_required=True,
            t_hsr_stale_us=96_000,  # 96 ms stale threshold
        )
        self.state = initial_state()

        # Dummy valid proposal and forward ranges to isolate HSR behavior
        self.valid_proposal = Proposal(
            seq=1, sim_stamp_us=32_000, left_urad_s=2_000_000, right_urad_s=2_000_000
        )
        self.clean_ranges = [5.0] * 10  # 5.0m clear ahead

    def tearDown(self):
        self.recv_sock.close()
        self.send_sock.close()

    def test_nominal_telemetry_keeps_gate_in_run(self):
        """Verifies clear synthetic telemetry over UDP allows Gate to operate."""
        payload = build_payload(obs_id=1, sim_time_us=32_000, distress_permille=0)
        self.send_sock.sendto(payload, self.dest)

        pkt, count = drain_hsr_telemetry(self.recv_sock, t_rx_us=33_000)
        self.assertEqual(count, 1)
        self.assertIsNotNone(pkt)

        # Feed into Gate step
        inp = GateInputs(
            sim_time_us=32_000,
            proposal=self.valid_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=32_000,
            raw_valid_points=10,
            hsr_status=pkt.state,
            hsr_stamp_us=pkt.t_obs_us,
        )
        # First tick in TRIPPED (fail-closed start) begins dwell
        res = step(self.state, self.params, inp)
        self.assertNotEqual(res.reason, Reason.TRIP_HSR_INVALID)
        self.assertNotEqual(res.reason, Reason.TRIP_HSR_CRITICAL)
        self.assertNotEqual(res.reason, Reason.TRIP_HSR_STALE)

    def test_distress_spike_forces_immediate_critical_trip(self):
        """Verifies acute distress over UDP immediately commands 0 rad/s and trips CRITICAL."""
        payload = build_payload(obs_id=2, sim_time_us=64_000, distress_permille=850)
        self.send_sock.sendto(payload, self.dest)

        pkt, _ = drain_hsr_telemetry(self.recv_sock, t_rx_us=65_000)
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.state, "CRITICAL")

        inp = GateInputs(
            sim_time_us=64_000,
            proposal=self.valid_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=64_000,
            raw_valid_points=10,
            hsr_status=pkt.state,
            hsr_stamp_us=pkt.t_obs_us,
        )
        res = step(self.state, self.params, inp)
        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.reason, Reason.TRIP_HSR_CRITICAL)
        self.assertEqual(res.cmd_left_urad_s, 0)
        self.assertEqual(res.cmd_right_urad_s, 0)

    def test_burst_flood_prevents_critical_masking(self):
        """Verifies that within a multi-packet burst, CRITICAL is never masked by a trailing CLEAR."""
        p_clear_1 = build_payload(obs_id=10, sim_time_us=96_000, distress_permille=0)
        p_crit = build_payload(obs_id=11, sim_time_us=96_100, distress_permille=850)
        p_clear_2 = build_payload(obs_id=12, sim_time_us=96_200, distress_permille=0)

        # Transmit rapid burst into UDP buffer
        self.send_sock.sendto(p_clear_1, self.dest)
        self.send_sock.sendto(p_crit, self.dest)
        self.send_sock.sendto(p_clear_2, self.dest)

        pkt, count = drain_hsr_telemetry(self.recv_sock, t_rx_us=97_000)
        self.assertEqual(count, 3)
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.obs_id, 11)
        self.assertEqual(pkt.state, "CRITICAL")

        inp = GateInputs(
            sim_time_us=96_200,
            proposal=self.valid_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=96_200,
            raw_valid_points=10,
            hsr_status=pkt.state,
            hsr_stamp_us=pkt.t_obs_us,
        )
        res = step(self.state, self.params, inp)
        self.assertEqual(res.reason, Reason.TRIP_HSR_CRITICAL)

    def test_stale_hang_trips_hsr_watchdog(self):
        """Verifies that silenced telemetry (>96ms) trips Reason.TRIP_HSR_STALE fail-closed."""
        # Previous reading at t = 100,000 µs
        prev_obs_us = 100_000
        now_us = prev_obs_us + 100_000  # 100 ms elapsed (> 96 ms stale threshold)

        # Socket receives nothing (stalled producer)
        pkt, count = drain_hsr_telemetry(self.recv_sock, t_rx_us=now_us)
        self.assertEqual(count, 0)
        self.assertIsNone(pkt)

        # Gate fed with stale held telemetry
        inp = GateInputs(
            sim_time_us=now_us,
            proposal=self.valid_proposal,
            ranges_m=self.clean_ranges,
            lidar_stamp_us=now_us,
            raw_valid_points=10,
            hsr_status="CLEAR",
            hsr_stamp_us=prev_obs_us,
        )
        res = step(self.state, self.params, inp)
        self.assertEqual(res.state.mode, Mode.TRIPPED)
        self.assertEqual(res.reason, Reason.TRIP_HSR_STALE)

    def test_frozen_frame_is_detected(self):
        """Verifies that an advancing clock with a repeated obs_id triggers the frozen detector."""
        last_seen_obs = 42
        # Producer sends new packet with updated sim time but frozen obs_id 42
        payload = build_payload(obs_id=42, sim_time_us=200_000, distress_permille=0)
        self.send_sock.sendto(payload, self.dest)

        pkt, _ = drain_hsr_telemetry(self.recv_sock, t_rx_us=201_000)
        self.assertIsNotNone(pkt)
        self.assertTrue(is_perception_frozen(pkt.obs_id, last_seen_obs))


if __name__ == "__main__":
    unittest.main()
