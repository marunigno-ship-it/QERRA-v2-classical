# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""Standard-library tests for HSR UDP receiver diagnostics."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Iterable, List, Union

# Ensure repository root is on sys.path when test is run directly or via discover
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gate.gate_ipc import MAX_DATAGRAM_BYTES
from ros2.hsr_receiver import HsrReceiver, MAX_REJECTION_REASON_CHARS


DatagramItem = Union[bytes, BaseException]


class FakeDatagramSocket:
    """Small deterministic non-blocking socket double for receiver unit tests."""

    def __init__(self, datagrams: Iterable[DatagramItem] = ()) -> None:
        self._datagrams: List[DatagramItem] = list(datagrams)
        self.closed = False

    def recvfrom(self, bufsize: int):
        if not self._datagrams:
            raise BlockingIOError

        item = self._datagrams.pop(0)
        if isinstance(item, BaseException):
            raise item

        # Match recvfrom()'s truncating behaviour on platforms that return the
        # available prefix when the supplied receive buffer is too small.
        return item[:bufsize], ("127.0.0.1", 50_008)

    def close(self) -> None:
        self.closed = True


class WindowsMessageTooLargeError(OSError):
    """Simulate WSAEMSGSIZE, raised by Windows for an oversized UDP datagram."""

    def __init__(self) -> None:
        super().__init__("simulated oversized UDP datagram")
        self.winerror = 10040


def valid_payload(**overrides) -> bytes:
    payload = {
        "obs_id": 1,
        "t_obs_us": 100_000,
        "t_emit_us": 101_000,
        "distress_permille": 0,
        "state": "CLEAR",
        "hazard_proximity": False,
        "persons_nearby_count": 2,
    }
    payload.update(overrides)
    return json.dumps(payload).encode("utf-8")


class HsrReceiverDiagnosticsTests(unittest.TestCase):
    def make_receiver(self, datagrams=()):
        sock = FakeDatagramSocket(datagrams)
        receiver = HsrReceiver(enabled=True, sock=sock)
        return receiver, sock

    def test_nominal_reception_increments_drained_only(self):
        receiver, _ = self.make_receiver([valid_payload()])

        status, stamp = receiver.poll(now_us=102_000)

        self.assertEqual((status, stamp), ("CLEAR", 100_000))
        self.assertEqual(receiver.packets_drained_total, 1)
        self.assertEqual(receiver.packets_rejected_total, 0)
        self.assertIsNone(receiver.last_rejection_reason)

    def test_oversized_datagram_is_rejected_and_counted(self):
        oversized = b"x" * (MAX_DATAGRAM_BYTES + 1)
        receiver, _ = self.make_receiver([oversized])

        receiver.poll(now_us=102_000)

        self.assertEqual(receiver.packets_drained_total, 1)
        self.assertEqual(receiver.packets_rejected_total, 1)
        self.assertEqual(receiver.last_rejection_reason, "oversized_datagram")

    def test_windows_message_too_large_error_is_counted_as_rejection(self):
        receiver, _ = self.make_receiver([WindowsMessageTooLargeError()])

        receiver.poll(now_us=102_000)

        self.assertEqual(receiver.packets_drained_total, 1)
        self.assertEqual(receiver.packets_rejected_total, 1)
        self.assertEqual(receiver.last_rejection_reason, "oversized_datagram")

    def test_missing_required_hazard_field_is_rejected(self):
        missing_hazard = valid_payload()
        data = json.loads(missing_hazard.decode("utf-8"))
        del data["hazard_proximity"]
        receiver, _ = self.make_receiver([json.dumps(data).encode("utf-8")])

        receiver.poll(now_us=102_000)

        self.assertEqual(receiver.packets_drained_total, 1)
        self.assertEqual(receiver.packets_rejected_total, 1)
        self.assertEqual(receiver.last_rejection_reason, "missing_required_field")

    def test_causal_and_future_timestamp_inversions_are_rejected(self):
        causal_inversion = valid_payload(t_obs_us=200_000, t_emit_us=199_999)
        future_observation = valid_payload(
            obs_id=2,
            t_obs_us=200_001,
            t_emit_us=200_002,
        )
        receiver, _ = self.make_receiver([causal_inversion, future_observation])

        receiver.poll(now_us=200_000)

        self.assertEqual(receiver.packets_drained_total, 2)
        self.assertEqual(receiver.packets_rejected_total, 2)
        self.assertEqual(
            receiver.last_rejection_reason,
            "future_observation_timestamp",
        )

    def test_declared_state_mismatch_is_rejected(self):
        mismatched = valid_payload(distress_permille=800, state="CLEAR")
        receiver, _ = self.make_receiver([mismatched])

        receiver.poll(now_us=102_000)

        self.assertEqual(receiver.packets_drained_total, 1)
        self.assertEqual(receiver.packets_rejected_total, 1)
        self.assertEqual(receiver.last_rejection_reason, "state_mismatch")

    def test_reset_clears_stream_state_but_preserves_lifetime_diagnostics(self):
        valid = valid_payload()
        missing_field_data = json.loads(valid.decode("utf-8"))
        missing_field_data["obs_id"] = 2
        del missing_field_data["hazard_proximity"]
        invalid = json.dumps(missing_field_data).encode("utf-8")
        receiver, _ = self.make_receiver([valid, invalid])

        status, stamp = receiver.poll(now_us=102_000)
        self.assertEqual((status, stamp), ("CLEAR", 100_000))
        self.assertEqual(receiver.last_obs_id, 1)
        self.assertEqual(receiver.packets_drained_total, 2)
        self.assertEqual(receiver.packets_rejected_total, 1)
        self.assertEqual(receiver.last_rejection_reason, "missing_required_field")

        drained_before_reset = receiver.packets_drained_total
        rejected_before_reset = receiver.packets_rejected_total
        reason_before_reset = receiver.last_rejection_reason

        receiver.reset()

        self.assertIsNone(receiver.last_status)
        self.assertIsNone(receiver.last_stamp_us)
        self.assertIsNone(receiver.last_obs_id)
        self.assertFalse(receiver.frozen_latched)
        self.assertFalse(receiver.rebase_in_progress)
        self.assertEqual(receiver.rebase_streak, 0)
        self.assertEqual(receiver.packets_drained_total, drained_before_reset)
        self.assertEqual(receiver.packets_rejected_total, rejected_before_reset)
        self.assertEqual(receiver.last_rejection_reason, reason_before_reset)

    def test_rejection_reason_is_bounded_and_does_not_echo_untrusted_value(self):
        attacker_controlled_value = "UNTRUSTED-" * 120
        malformed = valid_payload(obs_id=attacker_controlled_value)
        receiver, _ = self.make_receiver([malformed])

        receiver.poll(now_us=102_000)

        reason = receiver.last_rejection_reason
        self.assertIsNotNone(reason)
        self.assertLessEqual(len(reason), MAX_REJECTION_REASON_CHARS)
        self.assertNotIn("UNTRUSTED", reason)
        self.assertEqual(reason, "invalid_telemetry")


if __name__ == "__main__":
    unittest.main()
