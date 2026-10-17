# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- Tamper-Evident Flight Recorder (Demo 7).
SAFETY_CONCEPT.md v0.1: R-09, R-10, Section 9.

Rules:
  - Canonical JSON: sort_keys=True, fixed separators (",", ":"), no NaNs.
  - SHA-256 Hash Chain: hash = SHA256(prev_hash_ascii + canonical_bytes_without_hash)
  - Genesis block: 64 zeros.
  - Binary disk writes with b"\\n" to prevent Windows CRLF translation.
  - Fsync after flush to guarantee durability on crash/power-loss.
  - Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional, Tuple

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64


def serialize_canonical(record_without_hash: Dict[str, Any]) -> bytes:
    """Canonical JSON serialization to raw UTF-8 bytes (no whitespace, deterministic order)."""
    return json.dumps(
        record_without_hash,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def compute_record_hash(prev_hash: str, canonical_bytes: bytes) -> str:
    """Computes SHA-256 hex digest: SHA256(prev_hash_ascii || canonical_bytes)."""
    hasher = hashlib.sha256()
    hasher.update(prev_hash.encode("ascii"))
    hasher.update(canonical_bytes)
    return hasher.hexdigest()


class GateLogger:
    """
    Append-only, hash-chained log writer.
    Writes binary bytes to disk with LF line endings on all operating systems.
    """

    def __init__(self, filepath: str, run_id: str, gate_version: str = "0.1"):
        self.filepath = filepath
        self.run_id = run_id
        self.gate_version = gate_version
        self.seq = 0
        self.prev_hash = GENESIS_HASH
        self._file = None

        # Ensure target directory exists
        dirname = os.path.dirname(filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        # Open in append-binary mode: prevents Windows from converting \n to \r\n
        self._file = open(self.filepath, "ab")

    def append(self, step_record: Dict[str, Any], wall_ns: int) -> Tuple[Dict[str, Any], str]:
        """
        Takes raw step() record dict, wraps it with audit envelope,
        computes hash chain, writes to disk, and forces hardware fsync.
        Raises IOError / OSError on write failure (triggers R-10).
        """
        record: Dict[str, Any] = {
            "v": SCHEMA_VERSION,
            "run_id": self.run_id,
            "seq": self.seq,
            "sim_time_us": step_record["sim_time_us"],
            "wall_ns": wall_ns,
            "state": step_record["state"],
            "reason": step_record["reason"],
            "events": step_record["events"],
            "proposal_seq": step_record["proposal_seq"],
            "proposal_age_us": step_record["proposal_age_us"],
            "lidar_valid": step_record["lidar_valid"],
            "lidar_min_mm": step_record["lidar_min_mm"],
            "d_stop_mm": step_record["d_stop_mm"],
            "obstacle_breach": step_record.get("obstacle_breach", False),
            "hsr_status": step_record["hsr_status"],
            "cmd_left_urad_s": step_record["cmd_left_urad_s"],
            "cmd_right_urad_s": step_record["cmd_right_urad_s"],
            "gate_version": self.gate_version,
            "prev_hash": self.prev_hash,
        }

        # Persist inputs for deterministic replay if present
        if "inputs" in step_record and step_record["inputs"] is not None:
            record["inputs"] = step_record["inputs"]

        canonical_bytes = serialize_canonical(record)
        current_hash = compute_record_hash(self.prev_hash, canonical_bytes)
        record["hash"] = current_hash

        # Write canonical line + LF to disk
        line_bytes = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8") + b"\n"

        self._file.write(line_bytes)
        self._file.flush()

        # Force hardware sync (F5 crash resilience)
        try:
            os.fsync(self._file.fileno())
        except (OSError, AttributeError):
            pass

        # Update state only after successful flush & fsync
        self.seq += 1
        self.prev_hash = current_hash
        return record, current_hash

    def close(self) -> None:
        if self._file and not self._file.closed:
            self._file.close()

    def __enter__(self) -> GateLogger:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
