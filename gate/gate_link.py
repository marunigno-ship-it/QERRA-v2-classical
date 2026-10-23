# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- gate -> proposer state channel (Demo 7).
SAFETY_CONCEPT.md v0.1: section 3 ("Age of a proposal"), AR-5, AR-6, C-4.

WHY THIS MODULE EXISTS
  The safety concept defines a proposal's age as  sim_now - sim_stamp,  where sim_stamp is
  the SIM time of the gate snapshot the proposal was computed from, echoed back by the
  proposer. For the proposer to echo it, the gate has to tell the proposer what sim time it is.
  This module is that one-way channel. Without it the proposer can only stamp proposals with
  its own wall clock, and the gate's watchdog compares two unrelated clocks.

DESIGN RULES
  * Sockets are one-directional. The gate only SENDS here, the proposer only RECEIVES here.
    Receiving sockets never send, so a killed peer cannot cause WinError 10054 on them, and
    no ioctl is needed. (Python's socket.ioctl supports only SIO_RCVALL, SIO_KEEPALIVE_VALS
    and SIO_LOOPBACK_FAST_PATH, so SIO_UDP_CONNRESET cannot be switched off from Python.)
  * Sending never blocks and never raises. A failed send is reported as False and ignored.
  * Receiving is bounded: at most MAX_DRAIN_PER_CALL datagrams per call, so a flood cannot
    keep the caller busy.
  * Strict parsing: size cap, exact schema, ints only, NaN/Infinity rejected by a raising
    parse_constant (parse_constant=None would ACCEPT them).
Standard library only.
"""
from __future__ import annotations

import json
import socket
from typing import Optional, Tuple

DEFAULT_STATE_PORT = 5007
MAX_STATE_BYTES = 256
MAX_DRAIN_PER_CALL = 256
_SCHEMA_VERSION = 1


def _reject_constant(name: str):
    raise ValueError(f"non-finite JSON constant rejected: {name}")


def create_state_sender() -> socket.socket:
    """Unbound, non-blocking UDP socket used only for sending."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    return sock


def send_state(sock: socket.socket, sim_time_us: int,
               port: int = DEFAULT_STATE_PORT, host: str = "127.0.0.1") -> bool:
    """Send the current sim time to the proposer. Never raises. Returns True if the send was accepted."""
    try:
        payload = json.dumps(
            {"v": _SCHEMA_VERSION, "sim_time_us": int(sim_time_us)}, separators=(",", ":")
        ).encode("utf-8")
        sock.sendto(payload, (host, port))
        return True
    except (OSError, ValueError, TypeError, OverflowError):
        return False


def create_state_receiver(port: int = DEFAULT_STATE_PORT, host: str = "127.0.0.1") -> socket.socket:
    """Non-blocking UDP socket bound to localhost, used only for receiving."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    sock.bind((host, port))
    return sock


def parse_state_datagram(raw: bytes) -> Optional[int]:
    """Return sim_time_us, or None if the datagram is oversized, malformed or not exactly the expected schema."""
    if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_STATE_BYTES:
        return None
    try:
        data = json.loads(bytes(raw).decode("utf-8"), parse_constant=_reject_constant)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    if not isinstance(data, dict) or set(data.keys()) != {"v", "sim_time_us"}:
        return None
    v, t = data["v"], data["sim_time_us"]
    if isinstance(v, bool) or not isinstance(v, int) or v != _SCHEMA_VERSION:
        return None
    if isinstance(t, bool) or not isinstance(t, int) or t < 0:
        return None
    return t


def drain_state(sock: socket.socket) -> Tuple[Optional[int], int]:
    """
    Drain pending state datagrams without blocking.
    Returns (largest valid sim_time_us seen, datagrams drained).
    Sim time only moves forward, so the largest value is the newest.
    """
    newest: Optional[int] = None
    count = 0
    for _ in range(MAX_DRAIN_PER_CALL):
        try:
            data, _addr = sock.recvfrom(MAX_STATE_BYTES + 1)
        except (BlockingIOError, InterruptedError):
            break
        except OSError as exc:
            err = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
            if err in (10054, 10040):          # peer reset / message too big on Windows: skip it
                count += 1
                continue
            break
        count += 1
        t = parse_state_datagram(data)
        if t is not None and (newest is None or t > newest):
            newest = t
    return newest, count
