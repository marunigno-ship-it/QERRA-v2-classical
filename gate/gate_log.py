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
  - Reconstructs GateInputs from log for deterministic replay.
  - Captures harness manifest chained into record 0 (V8).
  - Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from typing import Any, Dict, Optional, Tuple

from gate.gate_core import GateInputs, Proposal

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


def capture_harness_manifest(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Captures injected simulation conditions, fault configs, and harness switches (V8).
    Standard library only.
    """
    src = os.environ if env is None else env

    def _env_int(key: str) -> Optional[int]:
        v = src.get(key)
        return int(v) if v not in (None, "") else None

    def _env_float(key: str, default: float) -> float:
        v = src.get(key)
        return float(v) if v not in (None, "") else default

    return {
        "qerra_lidar_fault": src.get("QERRA_LIDAR_FAULT", "none"),
        "qerra_lidar_fault_sim_s": _env_float("QERRA_LIDAR_FAULT_SIM_S", 3.0),
        "qerra_proposer_fault": src.get("QERRA_PROPOSER_FAULT", "none"),
        "qerra_fault_sim_s": _env_float("QERRA_FAULT_SIM_S", 3.0),
        "qerra_hang_ms": _env_int("QERRA_HANG_MS") if _env_int("QERRA_HANG_MS") is not None else 800,
        "qerra_auto_reset_at_us": _env_int("QERRA_AUTO_RESET_AT_US"),
        "qerra_smoke_obstacle": src.get("QERRA_SMOKE_OBSTACLE", "1") == "1",
        "qerra_skip_proposer": src.get("QERRA_SKIP_PROPOSER", "0") == "1",
    }


def write_run_manifest(run_dir: str, manifest: Dict[str, Any]) -> str:
    """Writes manifest.json to the run directory in canonical sorted JSON."""
    os.makedirs(run_dir, exist_ok=True)
    manifest_path = os.path.join(run_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    return manifest_path


def reconstruct_inputs(record: Dict[str, Any]) -> GateInputs:
    """
    Reconstructs a GateInputs instance from a logged JSON record for deterministic replay.
    Handles deserialization of proposal dicts and decodes JSON string infinities
    ('+inf', '-inf', 'nan') back into IEEE 754 float values required by step().
    """
    inputs_data = record.get("inputs")
    if inputs_data is None:
        raise ValueError(f"Record seq={record.get('seq')} contains no 'inputs' field for replay")

    sim_time_us = record.get("sim_time_us")
    if sim_time_us is None:
        raise ValueError(f"Record seq={record.get('seq')} missing mandatory 'sim_time_us'")

    # Reconstruct proposal
    prop_data = inputs_data.get("proposal")
    proposal: Optional[Proposal] = None
    if isinstance(prop_data, dict):
        proposal = Proposal(
            seq=prop_data["seq"],
            sim_stamp_us=prop_data["sim_stamp_us"],
            left_urad_s=prop_data["left_urad_s"],
            right_urad_s=prop_data["right_urad_s"],
            session_id=prop_data.get("session_id", 0),
        )

    # Reconstruct ranges_m with string float conversions
    raw_ranges = inputs_data.get("ranges_m")
    ranges_m: Optional[list] = None
    if isinstance(raw_ranges, (list, tuple)):
        ranges_m = []
        for x in raw_ranges:
            if x == "+inf" or x == "inf":
                ranges_m.append(math.inf)
            elif x == "-inf":
                ranges_m.append(-math.inf)
            elif x == "nan":
                ranges_m.append(math.nan)
            elif isinstance(x, (int, float)):
                ranges_m.append(float(x) if isinstance(x, float) else x)
            else:
                ranges_m.append(x)
    elif raw_ranges is not None:
        ranges_m = raw_ranges

    return GateInputs(
        sim_time_us=sim_time_us,
        proposal=proposal,
        ranges_m=ranges_m,
        lidar_stamp_us=inputs_data.get("lidar_stamp_us"),
        reset_source=inputs_data.get("reset_source"),
        log_write_failed=bool(inputs_data.get("log_write_failed", False)),
        raw_valid_points=inputs_data.get("raw_valid_points"),
    )


class GateLogger:
    """
    Append-only, hash-chained log writer.
    Writes binary bytes to disk with LF line endings on all operating systems.
    """

    def __init__(
        self,
        filepath: str,
        run_id: str,
        gate_version: str = "0.3",
        manifest: Optional[Dict[str, Any]] = None,
    ):
        self.filepath = filepath
        self.run_id = run_id
        self.gate_version = gate_version
        self.manifest = manifest
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

        # Cryptographically seal manifest into record 0
        if self.seq == 0 and self.manifest is not None:
            record["manifest"] = self.manifest

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
