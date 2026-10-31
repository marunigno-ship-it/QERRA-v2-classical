# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Pure-Python HSR Telemetry Ingestion Receiver for the QERRA Supervisory Gate.

Decoupled from ROS 2 and rclpy so it executes and tests identically on Windows
development hosts and Linux CI environments.

Encapsulates non-blocking UDP socket reception, worst-severity batch reduction,
and timestamp tracking matching the Webots supervisory controller baseline.
"""
from __future__ import annotations

import socket
from typing import Optional, Tuple

from gate.gate_ipc import DEFAULT_HSR_PORT, create_udp_receiver, drain_hsr_telemetry
from gate.hsr_telemetry import HSRTelemetryPacket


class HsrReceiver:
    """
    Non-blocking HSR reflex telemetry receiver.
    Holds the latest valid HSR status and observation timestamp across ticks.
    """

    def __init__(
        self,
        port: int = DEFAULT_HSR_PORT,
        *,
        enabled: bool = True,
        sock: Optional[socket.socket] = None,
    ) -> None:
        self._port = port
        self._enabled = enabled
        self._sock = sock
        self._owns_sock = sock is None

        self._last_status: Optional[str] = None
        self._last_stamp_us: Optional[int] = None
        self._last_obs_id: Optional[int] = None
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
        return self._last_obs_id

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

    def poll(self, now_us: int) -> Tuple[Optional[str], Optional[int]]:
        """
        Polls and drains pending HSR telemetry datagrams for this control tick.

        Returns (hsr_status, hsr_stamp_us):
          - (None, None) if disabled or no valid packet has ever been received.
          - The held state and observation timestamp from the most recent valid batch.
        """
        if not self._enabled:
            return None, None

        if not self._ensure_socket():
            return self._last_status, self._last_stamp_us

        pkt, drained_count = drain_hsr_telemetry(self._sock, t_rx_us=now_us)
        self._packets_drained_total += drained_count

        if pkt is not None:
            self._last_status = pkt.state
            self._last_stamp_us = pkt.t_obs_us
            self._last_obs_id = pkt.obs_id

        return self._last_status, self._last_stamp_us

    def reset(self) -> None:
        """Clears held telemetry state (e.g. on operator reset)."""
        self._last_status = None
        self._last_stamp_us = None
        self._last_obs_id = None

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

    # 2. Ephemeral loopback test
    # Bind an ephemeral port (port 0) for testing to prevent collisions
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    test_sock.setblocking(False)
    test_sock.bind(("127.0.0.1", 0))
    ephemeral_port = test_sock.getsockname()[1]

    rx = HsrReceiver(port=ephemeral_port, enabled=True, sock=test_sock)
    assert rx.poll(now_us=100_000) == (None, None), "Initial poll with empty buffer must be (None, None)"

    # 3. Transmit a valid CLEAR packet
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload_clear = json.dumps({
        "obs_id": 1,
        "t_obs_us": 100_000,
        "t_emit_us": 101_000,
        "distress_permille": 0,
        "state": "CLEAR",
    }).encode("utf-8")
    sender.sendto(payload_clear, ("127.0.0.1", ephemeral_port))

    status, stamp = rx.poll(now_us=102_000)
    assert status == "CLEAR", f"Expected CLEAR, got {status}"
    assert stamp == 100_000, f"Expected stamp 100000, got {stamp}"
    assert rx.last_obs_id == 1

    # 4. Transmit a CRITICAL distress spike
    payload_crit = json.dumps({
        "obs_id": 2,
        "t_obs_us": 132_000,
        "t_emit_us": 133_000,
        "distress_permille": 850,
        "state": "CRITICAL",
    }).encode("utf-8")
    sender.sendto(payload_crit, ("127.0.0.1", ephemeral_port))

    status, stamp = rx.poll(now_us=134_000)
    assert status == "CRITICAL", f"Expected CRITICAL, got {status}"
    assert stamp == 132_000, f"Expected stamp 132000, got {stamp}"

    # 5. Empty subsequent tick holds previous values
    status, stamp = rx.poll(now_us=164_000)
    assert status == "CRITICAL", "Held status must persist on idle tick"
    assert stamp == 132_000, "Held timestamp must persist on idle tick"

    rx.close()
    sender.close()
    print("[HSR RECEIVER SELF-TEST] 5/5 assertions PASSED cleanly.")


if __name__ == "__main__":
    _self_test()
