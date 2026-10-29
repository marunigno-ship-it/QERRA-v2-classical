# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- Non-Blocking UDP IPC Shell (Demo 7/8/9 & Phase 2).
SAFETY_CONCEPT.md v0.2: AR-5, AR-6, C-4, D-3.

Rules:
  - Non-blocking localhost UDP sockets.
  - Proposals: Drains pending datagrams in a tick and keeps strictly the newest valid one.
  - HSR Telemetry: Drains pending datagrams in a tick and keeps the WORST severity (CRITICAL > MONITOR > CLEAR).
  - Enforces max message size (MAX_DATAGRAM_BYTES) via buffer-length check.
  - Strictly rejects NaN, Infinity, non-ints, and malformed JSON.
  - Standard library only.
"""
from __future__ import annotations

import json
import socket
from typing import Optional, Tuple

from gate.gate_core import Proposal
from gate.hsr_telemetry import (
    HSRTelemetryPacket,
    drain_worst_severity,
    parse_hsr_telemetry,
)

DEFAULT_PROPOSAL_PORT = 5005
DEFAULT_OPERATOR_PORT = 5006
DEFAULT_HSR_PORT = 5008
MAX_DATAGRAM_BYTES = 2048
MAX_DRAIN_PER_CALL = 256


def _reject_constant(name: str):
    """Callback to strictly reject NaN, Infinity, -Infinity in JSON."""
    raise ValueError(f"Non-finite JSON constant rejected: {name}")


def create_udp_receiver(port: int, host: str = "127.0.0.1") -> socket.socket:
    """Creates a non-blocking UDP socket bound to localhost."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    sock.bind((host, port))
    return sock


def parse_proposal_datagram(raw_bytes: bytes) -> Optional[Proposal]:
    """
    Validates and parses a raw JSON datagram into a Proposal object.
    Rejects oversized packets, invalid JSON, NaN/Infinity, and non-int types.
    Returns Proposal or None.
    """
    if not isinstance(raw_bytes, (bytes, bytearray)):
        return None

    if len(raw_bytes) > MAX_DATAGRAM_BYTES:
        return None

    try:
        data = json.loads(bytes(raw_bytes).decode("utf-8"), parse_constant=_reject_constant)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    required_keys = ("seq", "sim_stamp_us", "left_urad_s", "right_urad_s")
    for k in required_keys:
        if k not in data:
            return None
        val = data[k]
        # Must be strictly int, not bool, not float
        if not isinstance(val, int) or isinstance(val, bool):
            return None

    session_id = data.get("session_id", 0)
    if not isinstance(session_id, int) or isinstance(session_id, bool) or session_id < 0:
        return None

    return Proposal(
        seq=data["seq"],
        sim_stamp_us=data["sim_stamp_us"],
        left_urad_s=data["left_urad_s"],
        right_urad_s=data["right_urad_s"],
        session_id=session_id,
    )


def drain_proposals(sock: socket.socket) -> Tuple[Optional[Proposal], int]:
    """
    AR-5: Drains pending datagrams with zero blocking, bounded by MAX_DRAIN_PER_CALL.
    Returns (newest_valid_proposal, total_packets_drained).
    Arbitrates across process restarts using session_id (F3).
    """
    newest_proposal: Optional[Proposal] = None
    count = 0

    for _ in range(MAX_DRAIN_PER_CALL):
        try:
            # Read MAX_DATAGRAM_BYTES + 1 to detect packets exceeding the buffer limit
            data, _ = sock.recvfrom(MAX_DATAGRAM_BYTES + 1)
        except (BlockingIOError, InterruptedError):
            break
        except OSError as e:
            err = getattr(e, "winerror", getattr(e, "errno", None))
            if err in (10054, 10040):  # Client reset or message truncated on Windows
                count += 1
                continue
            break

        count += 1
        if len(data) > MAX_DATAGRAM_BYTES:
            continue

        proposal = parse_proposal_datagram(data)
        if proposal is not None:
            if newest_proposal is None:
                newest_proposal = proposal
            elif proposal.session_id > newest_proposal.session_id:
                newest_proposal = proposal
            elif (
                proposal.session_id == newest_proposal.session_id
                and proposal.seq > newest_proposal.seq
            ):
                newest_proposal = proposal

    return newest_proposal, count


def drain_hsr_telemetry(
    sock: socket.socket,
    t_rx_us: int,
) -> Tuple[Optional[HSRTelemetryPacket], int]:
    """
    Drains pending HSR telemetry datagrams non-blocking, bounded by MAX_DRAIN_PER_CALL.
    Applies parse_hsr_telemetry with receipt timestamp t_rx_us.
    Folds all valid packets in the batch using worst-severity reduction.

    Returns (worst_packet_or_none, total_datagrams_drained).
    """
    valid_packets = []
    count = 0

    for _ in range(MAX_DRAIN_PER_CALL):
        try:
            data, _ = sock.recvfrom(MAX_DATAGRAM_BYTES + 1)
        except (BlockingIOError, InterruptedError):
            break
        except OSError as e:
            err = getattr(e, "winerror", getattr(e, "errno", None))
            if err in (10054, 10040):  # Client reset or message truncated on Windows
                count += 1
                continue
            break

        count += 1
        if len(data) > MAX_DATAGRAM_BYTES:
            continue

        try:
            pkt = parse_hsr_telemetry(data, t_rx_us=t_rx_us)
            valid_packets.append(pkt)
        except (ValueError, KeyError, TypeError):
            # Corrupted, malformed, or causality-violating datagrams are dropped
            continue

    winning_packet = drain_worst_severity(valid_packets)
    return winning_packet, count


def poll_operator_reset(sock: socket.socket) -> Optional[str]:
    """
    Polls the isolated operator reset socket (AR-4).
    Accepts only datagrams matching exact string 'operator'.
    """
    reset_found = None
    for _ in range(MAX_DRAIN_PER_CALL):
        try:
            data, _ = sock.recvfrom(512)
            msg = data.decode("utf-8", errors="ignore").strip()
            if msg == "operator":
                reset_found = "operator"
        except (BlockingIOError, InterruptedError):
            break
        except OSError:
            break

    return reset_found
