# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Pure-Python HSR Telemetry Ingestion Receiver for the QERRA Supervisory Gate.

Encapsulates non-blocking UDP socket reception, in-memory queue ingestion (for ROS 2
topics), per-packet monotonicity validation, sticky frozen-frame detection, controlled
producer-restart dwell, and bounded rejection diagnostics.

Standard library only. Zero ROS 2 or external dependencies.
"""
from __future__ import annotations

import json
import socket
from typing import List, Optional, Tuple, Union

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

# Keep published diagnostic text short and independent of untrusted wire data.
MAX_REJECTION_REASON_CHARS = 64


class HsrReceiver:
    """Non-blocking HSR reflex telemetry receiver with stream freshness monitoring.

    Supports dual ingestion pathways:
      1. Localhost UDP datagrams (for Webots simulation / legacy IPC).
      2. In-memory pushed payloads (for ROS 2 native /hsr/telemetry topic subscription).

    Holds the latest valid HSR status and observation timestamp across ticks,
    latching fail-closed on frozen frames or counter regressions. Datagram counters
    and the most recent rejection category are process-lifetime diagnostics and
    are intentionally preserved by reset().
    """

    def __init__(
        self,
        port: int = DEFAULT_HSR_PORT,
        *,
        enabled: bool = True,
        use_socket: bool = True,
        sock: Optional[socket.socket] = None,
        max_age_us: int = 96_000,
        required_rebase_streak: int = 5,
    ) -> None:
        self._port = port
        self._enabled = enabled
        self._use_socket = use_socket and enabled
        self._sock = sock
        self._owns_sock = sock is None and self._use_socket
        self._max_age_us = max_age_us
        self._required_rebase_streak = required_rebase_streak

        # In-memory queue for native topic ingestion
        self._queue: List[Union[str, bytes]] = []

        self._stream_state = HSRStreamState()
        self._last_status: Optional[str] = None
        self._last_stamp_us: Optional[int] = None

        # Lifetime diagnostics: reset() must never decrease these counters.
        self._packets_drained_total: int = 0
        self._packets_rejected_total: int = 0
        self._last_rejection_reason: Optional[str] = None
        self._socket_error: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def use_socket(self) -> bool:
        return self._use_socket

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
        """Total datagrams/messages removed from socket/queue during this process lifetime."""
        return self._packets_drained_total

    @property
    def packets_rejected_total(self) -> int:
        """Total rejected datagrams/messages during this process lifetime."""
        return self._packets_rejected_total

    @property
    def last_rejection_reason(self) -> Optional[str]:
        """Fixed, bounded category for the most recent rejected datagram/message."""
        return self._last_rejection_reason

    @property
    def socket_error(self) -> Optional[str]:
        return self._socket_error

    def push(self, payload: Union[str, bytes]) -> None:
        """Push an in-memory payload (e.g. from a ROS 2 native topic callback)."""
        if not self._enabled:
            return
        self._queue.append(payload)

    def _ensure_socket(self) -> bool:
        """Lazily binds the UDP receiver socket on first poll if socket mode is enabled."""
        if not self._enabled or not self._use_socket:
            return True
        if self._sock is not None:
            return True
        try:
            self._sock = create_udp_receiver(self._port)
            self._socket_error = None
            return True
        except OSError as exc:
            self._socket_error = str(exc)
            return False

    @staticmethod
    def _rejection_category(exc: BaseException) -> str:
        """Map parser failures to fixed categories without exposing untrusted wire text."""
        if isinstance(exc, UnicodeDecodeError):
            return "invalid_utf8"
        if isinstance(exc, json.JSONDecodeError):
            return "invalid_json"

        message = str(exc)
        if message.startswith("Missing required HSR telemetry field:"):
            return "missing_required_field"
        if message.startswith("Causal inversion:"):
            return "timestamp_causality_error"
        if message.startswith("Clock inversion / future frame:"):
            return "future_observation_timestamp"
        if message.startswith("State mismatch:"):
            return "state_mismatch"
        if message.startswith("Invalid declared state:"):
            return "invalid_declared_state"
        return "invalid_telemetry"

    def _record_rejection(self, reason: str) -> None:
        """Increment the lifetime rejection total and store bounded safe text."""
        self._packets_rejected_total += 1
        self._last_rejection_reason = str(reason)[:MAX_REJECTION_REASON_CHARS]

    def _drain_packets(self, t_rx_us: int) -> Tuple[List[HSRTelemetryPacket], int]:
        """Drain pending datagrams/messages in arrival order, bounded per control tick."""
        valid_packets: List[HSRTelemetryPacket] = []
        count = 0

        # 1. Drain from in-memory queue first (ROS 2 native topic pathway)
        while self._queue and count < MAX_DRAIN_PER_CALL:
            raw = self._queue.pop(0)
            count += 1
            if len(raw) > MAX_DATAGRAM_BYTES:
                self._record_rejection("oversized_datagram")
                continue
            try:
                packet = parse_hsr_telemetry(raw, t_rx_us=t_rx_us)
                valid_packets.append(packet)
            except (ValueError, KeyError, TypeError, RecursionError) as exc:
                self._record_rejection(self._rejection_category(exc))
                continue

        # 2. Drain from UDP socket if socket mode is active
        if self._use_socket and self._sock is not None:
            for _ in range(MAX_DRAIN_PER_CALL - count):
                try:
                    data, _ = self._sock.recvfrom(MAX_DATAGRAM_BYTES + 1)
                except (BlockingIOError, InterruptedError):
                    break
                except OSError as exc:
                    winerror = getattr(exc, "winerror", None)
                    error_number = winerror if winerror is not None else exc.errno

                    if error_number == 10054:
                        # WSAECONNRESET: ICMP port-unreachable indication; not a datagram.
                        continue
                    if error_number == 10040:
                        # WSAEMSGSIZE: Windows reports oversized datagram as socket error.
                        count += 1
                        self._record_rejection("oversized_datagram")
                        continue

                    self._socket_error = str(exc)
                    break

                count += 1
                if len(data) > MAX_DATAGRAM_BYTES:
                    self._record_rejection("oversized_datagram")
                    continue

                try:
                    packet = parse_hsr_telemetry(data, t_rx_us=t_rx_us)
                    valid_packets.append(packet)
                except (ValueError, KeyError, TypeError, RecursionError) as exc:
                    self._record_rejection(self._rejection_category(exc))
                    continue

        return valid_packets, count

    def flush(self) -> int:
        """Flush and purge pending messages and socket datagrams."""
        flushed = len(self._queue)
        self._queue.clear()

        if self._use_socket and self._sock is not None:
            for _ in range(MAX_DRAIN_PER_CALL):
                try:
                    self._sock.recvfrom(MAX_DATAGRAM_BYTES + 1)
                    flushed += 1
                except (BlockingIOError, InterruptedError):
                    break
                except OSError as exc:
                    winerror = getattr(exc, "winerror", None)
                    error_number = winerror if winerror is not None else exc.errno
                    if error_number == 10040:
                        flushed += 1
                        continue
                    if error_number == 10054:
                        continue
                    break
        return flushed

    def poll(self, now_us: int) -> Tuple[Optional[str], Optional[int]]:
        """Poll HSR telemetry and return (status, observation_timestamp)."""
        if not self._enabled:
            return None, None

        if not self._ensure_socket():
            return self._last_status, self._last_stamp_us

        packets, drained_count = self._drain_packets(t_rx_us=now_us)
        self._packets_drained_total += drained_count

        # Step the pure stream monitor state machine.
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
        """Reset stream state without erasing process-lifetime diagnostics."""
        self.flush()
        self._stream_state = HSRStreamState()
        self._last_status = None
        self._last_stamp_us = None

    def close(self) -> None:
        """Release the UDP socket and clear in-memory buffers."""
        self._queue.clear()
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
    print("[HSR RECEIVER DIAGNOSTICS SELF-TEST] Running standalone checks...")

    # 1. Disabled receiver returns (None, None).
    rx_disabled = HsrReceiver(enabled=False)
    status, stamp = rx_disabled.poll(100_000)
    assert status is None and stamp is None, "Disabled receiver must return (None, None)"
    rx_disabled.close()

    # 2. Ephemeral loopback UDP receiver setup.
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    test_sock.setblocking(False)
    test_sock.bind(("127.0.0.1", 0))
    ephemeral_port = test_sock.getsockname()[1]

    rx = HsrReceiver(port=ephemeral_port, enabled=True, sock=test_sock)
    assert rx.poll(now_us=100_000) == (None, None), "Empty buffer must return (None, None)"

    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    destination = ("127.0.0.1", ephemeral_port)

    # 3. Transmit a valid CLEAR packet over UDP.
    payload_clear = json.dumps({
        "obs_id": 1,
        "t_obs_us": 100_000,
        "t_emit_us": 101_000,
        "distress_permille": 0,
        "state": "CLEAR",
        "hazard_proximity": False,
        "persons_nearby_count": 2,
    }).encode("utf-8")
    sender.sendto(payload_clear, destination)

    status, stamp = rx.poll(now_us=102_000)
    assert status == HSR_CLEAR, f"Expected CLEAR, got {status}"
    assert stamp == 100_000, f"Expected stamp 100000, got {stamp}"
    assert rx.last_obs_id == 1
    assert rx.packets_drained_total == 1
    assert rx.packets_rejected_total == 0

    # 4. Missing required hazard_proximity field is rejected and categorized.
    payload_missing = json.dumps({
        "obs_id": 2,
        "t_obs_us": 105_000,
        "t_emit_us": 106_000,
        "distress_permille": 0,
        "persons_nearby_count": 2,
    }).encode("utf-8")
    sender.sendto(payload_missing, destination)

    status, stamp = rx.poll(now_us=107_000)
    assert status == HSR_CLEAR, "A rejected packet must not replace the held valid status"
    assert rx.packets_rejected_total == 1
    assert rx.last_rejection_reason == "missing_required_field"

    # 5. Transmit an advancing CRITICAL distress packet.
    payload_critical = json.dumps({
        "obs_id": 3,
        "t_obs_us": 132_000,
        "t_emit_us": 133_000,
        "distress_permille": 850,
        "state": "CRITICAL",
        "hazard_proximity": False,
        "persons_nearby_count": 2,
    }).encode("utf-8")
    sender.sendto(payload_critical, destination)

    status, stamp = rx.poll(now_us=134_000)
    assert status == HSR_CRITICAL, f"Expected CRITICAL, got {status}"
    assert stamp == 132_000, f"Expected stamp 132000, got {stamp}"
    assert rx.last_obs_id == 3

    # 6. In-Memory Queue Push Verification (ROS 2 native topic pathway, use_socket=False)
    rx_topic = HsrReceiver(enabled=True, use_socket=False)
    assert rx_topic.use_socket is False
    assert rx_topic._sock is None, "Topic receiver must never instantiate a UDP socket"

    # Push valid packet via in-memory topic pathway
    payload_topic = json.dumps({
        "obs_id": 1,
        "t_obs_us": 200_000,
        "t_emit_us": 201_000,
        "distress_permille": 0,
        "state": "CLEAR",
        "hazard_proximity": False,
        "persons_nearby_count": 2,
    })
    rx_topic.push(payload_topic)
    status_t, stamp_t = rx_topic.poll(now_us=202_000)
    assert status_t == HSR_CLEAR and stamp_t == 200_000
    assert rx_topic.packets_drained_total == 1

    # Push duplicate frame via in-memory pathway -> must latch freeze
    rx_topic.push(payload_topic)
    status_t2, stamp_t2 = rx_topic.poll(now_us=234_000)
    assert rx_topic.frozen_latched is True
    assert status_t2 is None and stamp_t2 is None
    rx_topic.close()

    # 7. Repeated obs_id detects a frozen frame and clears the held status (UDP)
    payload_frozen = json.dumps({
        "obs_id": 3,
        "t_obs_us": 165_000,
        "t_emit_us": 166_000,
        "distress_permille": 0,
        "state": "CLEAR",
        "hazard_proximity": False,
        "persons_nearby_count": 2,
    }).encode("utf-8")
    sender.sendto(payload_frozen, destination)

    status, stamp = rx.poll(now_us=167_000)
    assert status is None and stamp is None, "Frozen frame must clear status to trip the Gate"
    assert rx.frozen_latched is True

    # 8. Reset clears stream state but preserves lifetime diagnostic history.
    drained_before_reset = rx.packets_drained_total
    rejected_before_reset = rx.packets_rejected_total
    reason_before_reset = rx.last_rejection_reason
    rx.reset()
    assert rx.frozen_latched is False
    assert rx.last_obs_id is None
    assert rx.last_status is None and rx.last_stamp_us is None
    assert rx.packets_drained_total == drained_before_reset
    assert rx.packets_rejected_total == rejected_before_reset
    assert rx.last_rejection_reason == reason_before_reset

    rx.close()
    test_sock.close()
    sender.close()
    print("[HSR RECEIVER DIAGNOSTICS SELF-TEST] All assertion suites PASSED cleanly.")


if __name__ == "__main__":
    _self_test()
