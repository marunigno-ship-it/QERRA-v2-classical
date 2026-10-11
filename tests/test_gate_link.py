# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
Tests for gate/gate_link.py (gate -> proposer state channel) and a loopback round trip.
Run from the repository root:
    python -m unittest tests.test_gate_link -v
"""
import json
import socket
import time
import unittest

from gate.gate_link import (
    MAX_DRAIN_PER_CALL, MAX_STATE_BYTES, create_state_receiver, create_state_sender,
    drain_state, parse_state_datagram, send_state,
)


def free_udp_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def good(t=1000, v=1):
    return json.dumps({"v": v, "sim_time_us": t}).encode()


class TestParse(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_state_datagram(good(32000)), 32000)
        self.assertEqual(parse_state_datagram(good(0)), 0)

    def test_rejects_bad_input(self):
        cases = {
            "nan": b'{"v":1,"sim_time_us":NaN}',
            "inf": b'{"v":1,"sim_time_us":Infinity}',
            "neg_inf": b'{"v":1,"sim_time_us":-Infinity}',
            "nan_in_extra_key": b'{"v":1,"sim_time_us":5,"x":NaN}',
            "extra_key": b'{"v":1,"sim_time_us":5,"x":1}',
            "missing_key": b'{"v":1}',
            "float_time": b'{"v":1,"sim_time_us":1.5}',
            "bool_time": b'{"v":1,"sim_time_us":true}',
            "string_time": b'{"v":1,"sim_time_us":"5"}',
            "negative_time": b'{"v":1,"sim_time_us":-1}',
            "wrong_version": good(5, v=2),
            "bool_version": b'{"v":true,"sim_time_us":5}',
            "not_dict": b"[1,2,3]",
            "not_json": b"XXXX",
            "bad_utf8": b"\xff\xfe\x00",
            "empty": b"",
            "oversized": b"X" * (MAX_STATE_BYTES + 1),
            "deep_nesting": b"[" * 5000 + b"]" * 5000,
            "not_bytes": "text",
        }
        for name, raw in cases.items():
            with self.subTest(case=name):
                self.assertIsNone(parse_state_datagram(raw))


class TestLoopback(unittest.TestCase):
    def setUp(self):
        self.port = free_udp_port()
        self.rx = create_state_receiver(self.port)
        self.tx = create_state_sender()

    def tearDown(self):
        self.rx.close()
        self.tx.close()

    def _wait_drain(self, expect_count, timeout=1.0):
        deadline = time.time() + timeout
        total_newest, total_count = None, 0
        while time.time() < deadline and total_count < expect_count:
            newest, count = drain_state(self.rx)
            total_count += count
            if newest is not None and (total_newest is None or newest > total_newest):
                total_newest = newest
            time.sleep(0.002)
        return total_newest, total_count

    def test_round_trip_and_newest_wins(self):
        for t in (32000, 96000, 64000):                      # out of order on purpose
            self.assertTrue(send_state(self.tx, t, port=self.port))
        newest, count = self._wait_drain(3)
        self.assertEqual(count, 3)
        self.assertEqual(newest, 96000)                      # largest sim time wins

    def test_empty_receive_does_not_block(self):
        t0 = time.perf_counter()
        newest, count = drain_state(self.rx)
        self.assertLess(time.perf_counter() - t0, 0.05)
        self.assertEqual((newest, count), (None, 0))

    def test_garbage_is_counted_but_ignored(self):
        raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        raw.sendto(b"X" * 1000, ("127.0.0.1", self.port))
        raw.sendto(b'{"v":1,"sim_time_us":NaN}', ("127.0.0.1", self.port))
        raw.sendto(good(777), ("127.0.0.1", self.port))
        raw.close()
        newest, count = self._wait_drain(3)
        self.assertEqual(count, 3)
        self.assertEqual(newest, 777)

    def test_flood_is_bounded_per_call(self):
        raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        n = MAX_DRAIN_PER_CALL * 3
        for i in range(n):
            raw.sendto(good(i), ("127.0.0.1", self.port))
        raw.close()
        time.sleep(0.05)
        t0 = time.perf_counter()
        newest, count = drain_state(self.rx)
        elapsed = time.perf_counter() - t0
        self.assertLessEqual(count, MAX_DRAIN_PER_CALL)      # never more than the cap in one call
        self.assertLess(elapsed, 0.5)

    def test_send_never_raises_even_to_a_dead_port(self):
        dead = free_udp_port()                               # nobody listens here
        for _ in range(20):
            self.assertIn(send_state(self.tx, 1, port=dead), (True, False))
        self.assertFalse(send_state(self.tx, "not an int", port=self.port))
        self.assertFalse(send_state(self.tx, float("nan"), port=self.port))


if __name__ == "__main__":
    unittest.main()
