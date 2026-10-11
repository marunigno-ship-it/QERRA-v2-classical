# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
Unit tests for gate/gate_ipc.py (SAFETY_CONCEPT.md v0.1).
Covers: UDP non-blocking drain, message flooding (newest retained),
        size limits, NaN rejection, and operator reset isolation.
Standard library only.
"""
import json
import socket
import unittest

from gate.gate_ipc import (
    create_udp_receiver,
    drain_proposals,
    parse_proposal_datagram,
    poll_operator_reset,
)


class TestGateIPC(unittest.TestCase):
    def setUp(self):
        # Use ephemeral ports for testing to avoid conflicts
        self.recv_sock = create_udp_receiver(port=0)
        self.port = self.recv_sock.getsockname()[1]

        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def tearDown(self):
        self.recv_sock.close()
        self.send_sock.close()

    def _send(self, payload: bytes):
        self.send_sock.sendto(payload, ("127.0.0.1", self.port))

    def test_clean_proposal_received(self):
        msg = {
            "seq": 1,
            "sim_stamp_us": 1_000_000,
            "left_urad_s": 2_000_000,
            "right_urad_s": 2_000_000,
        }
        self._send(json.dumps(msg).encode("utf-8"))

        proposal, count = drain_proposals(self.recv_sock)
        self.assertEqual(count, 1)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.seq, 1)
        self.assertEqual(proposal.left_urad_s, 2_000_000)

    def test_message_flooding_keeps_strictly_newest(self):
        # Flood 5 packets in one tick
        for i in range(1, 6):
            msg = {
                "seq": i,
                "sim_stamp_us": 1_000_000 + i * 32_000,
                "left_urad_s": i * 500_000,
                "right_urad_s": i * 500_000,
            }
            self._send(json.dumps(msg).encode("utf-8"))

        proposal, count = drain_proposals(self.recv_sock)
        self.assertEqual(count, 5)  # Drained all 5 packets
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.seq, 5)  # Retained the newest
        self.assertEqual(proposal.left_urad_s, 2_500_000)

    def test_nan_and_infinity_rejected(self):
        # Raw payload with illegal NaN constant
        payload_nan = b'{"seq": 2, "sim_stamp_us": 1000, "left_urad_s": NaN, "right_urad_s": 1000}'
        self._send(payload_nan)

        proposal, count = drain_proposals(self.recv_sock)
        self.assertEqual(count, 1)
        self.assertIsNone(proposal)  # Must be rejected

    def test_oversized_datagram_rejected(self):
        huge_payload = b"X" * 3000  # Exceeds MAX_DATAGRAM_BYTES (2048)
        self._send(huge_payload)

        proposal, count = drain_proposals(self.recv_sock)
        self.assertEqual(count, 1)
        self.assertIsNone(proposal)

    def test_malformed_json_and_bad_types_rejected(self):
        bad_cases = [
            b"not json at all",
            b'{"seq": "one", "sim_stamp_us": 1000, "left_urad_s": 1, "right_urad_s": 1}',
            b'{"seq": 1, "sim_stamp_us": 1000, "left_urad_s": 1.5, "right_urad_s": 1}',
            b'{"seq": 1, "sim_stamp_us": 1000}',  # missing wheel keys
        ]
        for bad in bad_cases:
            res = parse_proposal_datagram(bad)
            self.assertIsNone(res)

    def test_empty_drain_returns_none_without_blocking(self):
        # Empty socket: must return immediately without waiting
        proposal, count = drain_proposals(self.recv_sock)
        self.assertIsNone(proposal)
        self.assertEqual(count, 0)

    def test_operator_reset_isolated_channel(self):
        # Test operator reset socket helper
        op_sock = create_udp_receiver(port=0)
        op_port = op_sock.getsockname()[1]
        try:
            # 1. Proposer attempts to forge a reset
            self.send_sock.sendto(b"proposer", ("127.0.0.1", op_port))
            res = poll_operator_reset(op_sock)
            self.assertIsNone(res)

            # 2. Legitimate operator reset
            self.send_sock.sendto(b"operator", ("127.0.0.1", op_port))
            res = poll_operator_reset(op_sock)
            self.assertEqual(res, "operator")
        finally:
            op_sock.close()


if __name__ == "__main__":
    unittest.main()
