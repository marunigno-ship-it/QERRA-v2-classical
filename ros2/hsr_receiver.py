# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Pure-Python HSR Telemetry Ingestion Receiver for the QERRA Supervisory Gate.

Decoupled from ROS 2 and rclpy so it executes and tests identically on Windows
development hosts and Linux CI environments.

Encapsulates non-blocking UDP socket reception, per-packet monotonicity validation,
sticky frozen-frame detection, and controlled producer-restart dwell.
"""
from __future__ import annotations

import socket
from typing import List, Optional, Tuple

from gate.gate_ipc import (
    DEFAULT_HSR_PORT,
    MAX_DATAGRAM_BYTES,
    MAX_DRAIN_PER_CALL,
    create_udp_receiver,
)
from gate.hsr_telemetry import (
    HSRTelemetryPacket,
    HSRStreamState,
    parse_hsr_telemetry,
    step_hsr_stream,
    HSR_CLEAR,
    HSR_MONITOR,
    HSR_CRITICAL,
)


class HsrReceiver:
    """
    Non-blocking HSR reflex telemetry receiver with stream freshness monitoring.
    Holds the latest valid HSR status and observation timestamp across ticks,
    latching fail-closed on frozen frames or counter regressions.
    """

    def __init__(
        self,
        port: int = DEFAULT_HSR_PORT,
        *,
        enabled: bool = True,
        sock: Optional[socket.socket] = None,
        max_age_us: int = 96_000,
        required_rebase_streak: int = 5,
    ) -> None:
        self._port = port
        self._enabled = enabled
        self._sock = sock
        self._owns_sock = sock is None
        self._max_age_us = max_age_us
        self._required_rebase_streak = required_rebase_streak

        self._stream_state = HSRStreamState()
        self._last_status: Optional[str] = None
        self._last_stamp_us: Optional[int] = None
        self._packets_drained_total: int = 0
        self._socket_error: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def port(self) -> int:
        return self._port

    @property
    def last_status(self) -> Optional[str]:
        return self._last_status

    @property
    def last_stamp_us(self) -> Optional[int]:
        return self._last_stamp_us

    @property
    def last_obs_id(self) -> Optional[int]:
        return self._stream_state.last_seen_obs_id

    @property
    def frozen_latched(self) -> bool:
        return self._stream_state.frozen_latched

    @property
    def rebase_in_progress(self) -> bool:
        return self._stream_state.rebase_in_progress

    @property
    def rebase_streak(self) -> int:
        return self._stream_state.rebase_streak

    @property
    def packets_drained_total(self) -> int:
        return self._packets_drained_total

    @property
    def socket_error(self) -> Optional[str]:
        return self._socket_error

    def _ensure_socket(self) -> bool:
        """Lazily binds the UDP receiver socket on first poll if enabled."""
        if not self._enabled:
            return False
        if self._sock is not None:
            return True
        try:
            self._sock = create_udp_receiver(self._port)
            self._socket_error = None
            return True
        except OSError as exc:
            self._socket_error = str(exc)
            return False

    def _drain_packets(self, t_rx_us: int) -> Tuple[List[HSRTelemetryPacket], int]:
        """
        Drains all pending datagrams in arrival order without pre-mature reduction.
        Enforces MAX_DRAIN_PER_CALL limit per tick.
        """
        valid_packets: List[HSRTelemetryPacket] = []
        count = 0
        if self._sock is None:
            return valid_packets, 0

        for _ in range(MAX_DRAIN_PER_CALL):
            try:
                data, _ = self._sock.recvfrom(MAX_DATAGRAM_BYTES + 1)
            except (BlockingIOError, InterruptedError):
                break
            except OSError as e:
                err = getattr(e, "winerror", getattr(e, "errno", None))
                if err in (10054, 10040):  # Client reset or truncated message on Windows
                    count += 1
                    continue
                self._socket_error = str(e)
                break

            count += 1
            if len(data) > MAX_DATAGRAM_BYTES:
                continue

            try:
                pkt = parse_hsr_telemetry(data, t_rx_us=t_rx_us)
                valid_packets.append(pkt)
            except (ValueError, KeyError, TypeError):
                continue

        return valid_packets, count

    def flush(self) -> int:
        """Flushes and purges all pending datagrams from the OS socket buffer."""
        if self._sock is None:
            return 0
        flushed = 0
        for _ in range(MAX_DRAIN_PER_CALL):
            try:
                data, _ = self._sock.recvfrom(MAX_DATAGRAM_BYTES + 1)
                flushed += 1
            except (BlockingIOError, InterruptedError, OSError):
                break
        return flushed

    def poll(self, now_us: int) -> Tuple[Optional[str], Optional[int]]:
        """
        Polls and drains pending HSR telemetry datagrams for this control tick.

        Evaluates per-packet freshness and sequence continuity before reduction.
        Returns (hsr_status, hsr_stamp_us):
          - (None, None) if disabled, in fault (frozen/rebase), or never initialized.
          - The held state and observation timestamp from nominal operation.
        """
        if not self._enabled:
            return None, None

        if not self._ensure_socket():
            return self._last_status, self._last_stamp_us

        packets, drained_count = self._drain_packets(t_rx_us=now_us)
        self._packets_drained_total += drained_count

        # Step the pure stream monitor state machine
        self._stream_state, status, stamp = step_hsr_stream(
            self._stream_state,
            packets,
            now_us=now_us,
            max_age_us=self._max_age_us,
            required_streak=self._required_rebase_streak,
        )

        self._last_status = status
        self._last_stamp_us = stamp

        return self._last_status, self._last_stamp_us

    def reset(self) -> None:
        """Clears held telemetry state, flushes socket buffer, and resets stream monitor."""
        self.flush()
        self._stream_state = HSRStreamState()
        self._last_status = None
        self._last_stamp_us = None

    def close(self) -> None:
        """Releases the UDP socket if owned by this receiver."""
        if self._owns_sock and self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


# ----------------------------------------------------------------------------
# Standalone Local Verification (Run directly on Windows without ROS 2)
# ----------------------------------------------------------------------------
def _self_test() -> None:
    import json

    print("[HSR RECEIVER SELF-TEST] Running standalone checks...")

    # 1. Disabled receiver returns (None, None)
    rx_disabled = HsrReceiver(enabled=False)
    status, stamp = rx_disabled.poll(100_000)
    assert status is None and stamp is None, "Disabled receiver must return (None, None)"
    rx_disabled.close()

    # 2. Ephemeral loopback receiver setup
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    test_sock.setblocking(False)
    test_sock.bind(("127.0.0.1", 0))
    ephemeral_port = test_sock.getsockname()[1]

    rx = HsrReceiver(port=ephemeral_port, enabled=True, sock=test_sock)
    assert rx.poll(now_us=100_000) == (None, None), "Initial poll with empty buffer must be (None, None)"

    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = ("127.0.0.1", ephemeral_port)

    # 3. Transmit a valid CLEAR packet
    payload_clear = json.dumps({
        "obs_id": 1,
        "t_obs_us": 100_000,
        "t_emit_us": 101_000,
        "distress_permille": 0,
        "state": "CLEAR",
    }).encode("utf-8")
    sender.sendto(payload_clear, dest)

    status, stamp = rx.poll(now_us=102_000)
    assert status == "CLEAR", f"Expected CLEAR, got {status}"
    assert stamp == 100_000, f"Expected stamp 100000, got {stamp}"
    assert rx.last_obs_id == 1

    # 4. Transmit an advancing CRITICAL distress spike
    payload_crit = json.dumps({
        "obs_id": 2,
        "t_obs_us": 132_000,
        "t_emit_us": 133_000,
        "distress_permille": 850,
        "state": "CRITICAL",
    }).encode("utf-8")
    sender.sendto(payload_crit, dest)

    status, stamp = rx.poll(now_us=134_000)
    assert status == "CRITICAL", f"Expected CRITICAL, got {status}"
    assert stamp == 132_000, f"Expected stamp 132000, got {stamp}"
    assert rx.last_obs_id == 2

    # 5. Empty subsequent tick holds previous values in nominal state
    status, stamp = rx.poll(now_us=164_000)
    assert status == "CRITICAL", "Held status must persist on nominal idle tick"
    assert stamp == 132_000, "Held timestamp must persist on nominal idle tick"

    # 6. Frozen frame detection: Repeated obs_id=2 at fresh time
    payload_frozen = json.dumps({
        "obs_id": 2,
        "t_obs_us": 165_000,
        "t_emit_us": 166_000,
        "distress_permille": 0,
        "state": "CLEAR",
    }).encode("utf-8")
    sender.sendto(payload_frozen, dest)

    status, stamp = rx.poll(now_us=167_000)
    assert status is None and stamp is None, "Frozen frame must clear status to trip gate"
    assert rx.frozen_latched is True, "Frozen latch must be set"

    # 7. Idle tick during freeze remains sticky fail-closed
    status, stamp = rx.poll(now_us=199_000)
    assert status is None and stamp is None, "Frozen latch must remain sticky on idle ticks"

    # 8. Reset clears latch and returns to clean state
    rx.reset()
    assert rx.frozen_latched is False
    assert rx.last_obs_id is None

    # 9. Producer restart & 5-tick dwell verification
    # Bring up to obs_id = 500
    p_up = json.dumps({"obs_id": 500, "t_obs_us": 200_000, "t_emit_us": 201_000, "distress_permille": 0, "state": "CLEAR"}).encode("utf-8")
    sender.sendto(p_up, dest)
    status, _ = rx.poll(now_us=202_000)
    assert status == "CLEAR" and rx.last_obs_id == 500

    # Producer restarts: obs_id drops to 0 (counter regression)
    p_rst = json.dumps({"obs_id": 0, "t_obs_us": 232_000, "t_emit_us": 233_000, "distress_permille": 0, "state": "CLEAR"}).encode("utf-8")
    sender.sendto(p_rst, dest)
    status, stamp = rx.poll(now_us=234_000)
    assert rx.rebase_in_progress is True
    assert rx.rebase_streak == 0
    assert status is None and stamp is None, "Producer restart must trip output to None immediately"

    # Burst of 3 packets in 1 tick only credits 1 streak
    for i in (1, 2, 3):
        p_b = json.dumps({"obs_id": i, "t_obs_us": 264_000, "t_emit_us": 265_000, "distress_permille": 0, "state": "CLEAR"}).encode("utf-8")
        sender.sendto(p_b, dest)
    status, _ = rx.poll(now_us=266_000)
    assert rx.rebase_streak == 1, "Burst in single tick must credit at most 1 streak"
    assert status is None

    # Ticks 2, 3, 4 with advancing CLEAR packets
    for i in range(2, 5):
        pkt = json.dumps({"obs_id": 3 + i, "t_obs_us": 264_000 + i * 32_000, "t_emit_us": 265_000 + i * 32_000, "distress_permille": 0, "state": "CLEAR"}).encode("utf-8")
        sender.sendto(pkt, dest)
        status, _ = rx.poll(now_us=266_000 + i * 32_000)
        assert rx.rebase_streak == i
        assert status is None

    # Tick 5 completes dwell
    pkt_fin = json.dumps({"obs_id": 8, "t_obs_us": 424_000, "t_emit_us": 425_000, "distress_permille": 0, "state": "CLEAR"}).encode("utf-8")
    sender.sendto(pkt_fin, dest)
    status, stamp = rx.poll(now_us=426_000)
    assert rx.rebase_in_progress is False
    assert rx.rebase_streak == 0
    assert status == "CLEAR" and stamp == 424_000, "5th clean tick must complete rebase and restore CLEAR"

    rx.close()
    sender.close()
    print("[HSR RECEIVER SELF-TEST] 9/9 assertions PASSED cleanly.")


if __name__ == "__main__":
    _self_test()
