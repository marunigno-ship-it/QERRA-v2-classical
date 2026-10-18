# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
Unit tests for gate/gate_ipc.py (SAFETY_CONCEPT.md v0.1).
Covers: UDP non-blocking drain, message flooding (newest retained),
        size limits, NaN rejection, session arbitration (F3),
        and operator reset isolation.
Standard library only.
"""
from __future__ import annotations

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

    # --- F3 Session Arbitration Tests ---

    def test_session_id_missing_defaults_to_zero(self):
        payload = {
            "seq": 1,
            "sim_stamp_us": 1_000_000,
            "left_urad_s": 100,
            "right_urad_s": 100,
        }
        res = parse_proposal_datagram(json.dumps(payload).encode("utf-8"))
        self.assertIsNotNone(res)
        self.assertEqual(res.session_id, 0)

    def test_session_id_invalid_types_and_negative_rejected(self):
        base = {
            "seq": 1,
            "sim_stamp_us": 1_000_000,
            "left_urad_s": 100,
            "right_urad_s": 100,
        }
        bad_session_ids = [-1, -100, True, False, 1.5, "1", [1], {"id": 1}, None]
        for bad_id in bad_session_ids:
            item = dict(base)
            item["session_id"] = bad_id
            raw = json.dumps(item).encode("utf-8")
            res = parse_proposal_datagram(raw)
            self.assertIsNone(res, f"Expected None for session_id={bad_id!r}")

    def test_session_arbitration_newer_session_replaces_older_regardless_of_seq(self):
        # Proposer incarnation 10 was at seq 500 when it terminated
        msg_old_session = {
            "session_id": 10,
            "seq": 500,
            "sim_stamp_us": 1_000_000,
            "left_urad_s": 100,
            "right_urad_s": 100,
        }
        # Proposer restarts with incarnation 11, starting at seq 0
        msg_new_session = {
            "session_id": 11,
            "seq": 0,
            "sim_stamp_us": 1_032_000,
            "left_urad_s": 200,
            "right_urad_s": 200,
        }
        self._send(json.dumps(msg_old_session).encode("utf-8"))
        self._send(json.dumps(msg_new_session).encode("utf-8"))

        proposal, count = drain_proposals(self.recv_sock)
        self.assertEqual(count, 2)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.session_id, 11)
        self.assertEqual(proposal.seq, 0)
        self.assertEqual(proposal.left_urad_s, 200)

    def test_session_arbitration_older_session_after_newer_rejected(self):
        # Newer session proposal arrives first
        msg_new_session = {
            "session_id": 20,
            "seq": 2,
            "sim_stamp_us": 1_032_000,
            "left_urad_s": 200,
            "right_urad_s": 200,
        }
        # Delayed/stale packet from old session arrives later with higher seq
        msg_old_session = {
            "session_id": 19,
            "seq": 999,
            "sim_stamp_us": 1_000_000,
            "left_urad_s": 100,
            "right_urad_s": 100,
        }
        self._send(json.dumps(msg_new_session).encode("utf-8"))
        self._send(json.dumps(msg_old_session).encode("utf-8"))

        proposal, count = drain_proposals(self.recv_sock)
        self.assertEqual(count, 2)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.session_id, 20)
        self.assertEqual(proposal.seq, 2)
        self.assertEqual(proposal.left_urad_s, 200)

    def test_session_arbitration_same_session_lower_seq_rejected(self):
        # Within the same session, out-of-order packet with lower seq must not overwrite newer seq
        msg_newer_seq = {
            "session_id": 5,
            "seq": 10,
            "sim_stamp_us": 1_320_000,
            "left_urad_s": 300,
            "right_urad_s": 300,
        }
        msg_older_seq = {
            "session_id": 5,
            "seq": 4,
            "sim_stamp_us": 1_128_000,
            "left_urad_s": 150,
            "right_urad_s": 150,
        }
        self._send(json.dumps(msg_newer_seq).encode("utf-8"))
        self._send(json.dumps(msg_older_seq).encode("utf-8"))

        proposal, count = drain_proposals(self.recv_sock)
        self.assertEqual(count, 2)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.session_id, 5)
        self.assertEqual(proposal.seq, 10)
        self.assertEqual(proposal.left_urad_s, 300)


if __name__ == "__main__":
    unittest.main()
