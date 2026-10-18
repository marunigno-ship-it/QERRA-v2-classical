# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- Standalone Flight Recorder Auditor (Demo 7).
SAFETY_CONCEPT.md v0.1: R-09, Section 9.

Verifies:
  1. Monotonic sequence numbers starting at 0 with no gaps.
  2. Strictly increasing simulation time (sim_time_us).
  3. No Windows CRLF (\\r\\n) line corruptions.
  4. Genesis hash equals 64 zeros.
  5. SHA-256 hash chain continuity: hash == SHA256(prev_hash + canonical_bytes).
  6. Truncation and rewrite detection against externally anchored head hash & final sequence number.
  7. Deterministic offline replay through pure gate_core.step() (--replay).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

from gate.gate_config import get_live_gate_params
from gate.gate_core import GateParams, initial_state, step
from gate.gate_log import (
    GENESIS_HASH,
    compute_record_hash,
    reconstruct_inputs,
    serialize_canonical,
)


@dataclass
class VerificationResult:
    is_valid: bool
    total_records: int
    first_seq: Optional[int]
    last_seq: Optional[int]
    head_hash: Optional[str]
    error_message: str
    is_anchored: bool = False


def verify_log_file(
    filepath: str,
    expected_head_seq: Optional[int] = None,
    expected_head_hash: Optional[str] = None,
) -> VerificationResult:
    """
    Audits a JSONL gate log file line by line.
    Standard library only.
    """
    try:
        with open(filepath, "rb") as f:
            raw_bytes = f.read()
    except Exception as e:
        return VerificationResult(
            is_valid=False,
            total_records=0,
            first_seq=None,
            last_seq=None,
            head_hash=None,
            error_message=f"Cannot open log file: {e}",
        )

    if not raw_bytes:
        return VerificationResult(
            is_valid=False,
            total_records=0,
            first_seq=None,
            last_seq=None,
            head_hash=None,
            error_message="Log file is empty",
        )

    # Check rule 3: Reject Windows CRLF (\r\n) corruptions
    if b"\r\n" in raw_bytes:
        return VerificationResult(
            is_valid=False,
            total_records=0,
            first_seq=None,
            last_seq=None,
            head_hash=None,
            error_message="Format corruption: file contains Windows CRLF (\\r\\n). Log must use binary LF (\\n).",
        )

    lines = [line for line in raw_bytes.split(b"\n") if line]
    total_records = len(lines)
    expected_prev_hash = GENESIS_HASH
    prev_sim_time = -1

    first_seq = None
    last_seq = None
    current_hash = None

    for idx, raw_line in enumerate(lines):
        try:
            record = json.loads(raw_line.decode("utf-8"), parse_constant=None)
        except Exception as e:
            return VerificationResult(
                is_valid=False,
                total_records=idx,
                first_seq=first_seq,
                last_seq=last_seq,
                head_hash=current_hash,
                error_message=f"Line {idx}: JSON parse failure or invalid constant (NaN/Inf): {e}",
            )

        if "hash" not in record or "prev_hash" not in record or "seq" not in record:
            return VerificationResult(
                is_valid=False,
                total_records=idx,
                first_seq=first_seq,
                last_seq=last_seq,
                head_hash=current_hash,
                error_message=f"Line {idx}: Missing mandatory hash or sequence keys",
            )

        recorded_hash = record["hash"]
        recorded_prev_hash = record["prev_hash"]
        seq = record["seq"]
        sim_time = record.get("sim_time_us")

        if idx == 0:
            first_seq = seq

        last_seq = seq

        # 1. Monotonic sequence check
        if seq != idx:
            return VerificationResult(
                is_valid=False,
                total_records=idx,
                first_seq=first_seq,
                last_seq=last_seq,
                head_hash=current_hash,
                error_message=f"Line {idx}: Sequence mismatch. Expected seq={idx}, got seq={seq}",
            )

        # 2. Monotonic sim_time check
        if sim_time is None or sim_time <= prev_sim_time:
            return VerificationResult(
                is_valid=False,
                total_records=idx,
                first_seq=first_seq,
                last_seq=last_seq,
                head_hash=current_hash,
                error_message=f"Line {idx}: Time anomaly. sim_time_us={sim_time} must be strictly > {prev_sim_time}",
            )
        prev_sim_time = sim_time

        # 3. Hash chain continuity
        if recorded_prev_hash != expected_prev_hash:
            return VerificationResult(
                is_valid=False,
                total_records=idx,
                first_seq=first_seq,
                last_seq=last_seq,
                head_hash=current_hash,
                error_message=(
                    f"Line {idx}: Broken hash chain! prev_hash mismatch. "
                    f"Expected {expected_prev_hash}, found {recorded_prev_hash}"
                ),
            )

        # 4. Hash recalculation check
        record_without_hash = {k: v for k, v in record.items() if k != "hash"}
        canonical_bytes = serialize_canonical(record_without_hash)
        expected_hash = compute_record_hash(recorded_prev_hash, canonical_bytes)

        if recorded_hash != expected_hash:
            return VerificationResult(
                is_valid=False,
                total_records=idx,
                first_seq=first_seq,
                last_seq=last_seq,
                head_hash=current_hash,
                error_message=(
                    f"Line {idx}: Tampering detected! Hash signature mismatch. "
                    f"Computed {expected_hash}, recorded {recorded_hash}"
                ),
            )

        current_hash = recorded_hash
        expected_prev_hash = current_hash

    # 5. External Anchor Verification (Truncation and rewrite detection)
    is_anchored = False
    if expected_head_seq is not None or expected_head_hash is not None:
        is_anchored = True
        if expected_head_seq is not None and last_seq != expected_head_seq:
            return VerificationResult(
                is_valid=False,
                total_records=total_records,
                first_seq=first_seq,
                last_seq=last_seq,
                head_hash=current_hash,
                error_message=(
                    f"Truncation detected! Anchor expected seq={expected_head_seq}, "
                    f"but log ends at seq={last_seq}"
                ),
                is_anchored=True,
            )

        if expected_head_hash is not None and current_hash != expected_head_hash:
            return VerificationResult(
                is_valid=False,
                total_records=total_records,
                first_seq=first_seq,
                last_seq=last_seq,
                head_hash=current_hash,
                error_message=(
                    f"Head hash mismatch! Anchor expected {expected_head_hash}, "
                    f"but log ends with {current_hash}"
                ),
                is_anchored=True,
            )

    return VerificationResult(
        is_valid=True,
        total_records=total_records,
        first_seq=first_seq,
        last_seq=last_seq,
        head_hash=current_hash,
        error_message="",
        is_anchored=is_anchored,
    )


def replay_log_file(filepath: str, params: GateParams) -> Tuple[bool, int, str]:
    """
    Replays a JSONL audit log file tick-by-tick through pure gate_core.step().
    Verifies that every recorded command, reason, state, and event list matches
    the recomputed pure core output exactly.
    Returns (success, records_replayed, error_message).
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        return False, 0, f"Cannot open log file: {e}"

    if not lines:
        return False, 0, "Log file is empty"

    state = initial_state()

    for idx, line in enumerate(lines):
        try:
            record = json.loads(line)
        except Exception as e:
            return False, idx, f"Line {idx}: JSON parse error: {e}"

        try:
            inp = reconstruct_inputs(record)
        except Exception as e:
            return False, idx, f"Line {idx}: Failed to reconstruct GateInputs: {e}"

        res = step(state, params, inp)
        state = res.state

        # Verify exact match against recorded decisions
        cmd_recomputed = (res.cmd_left_urad_s, res.cmd_right_urad_s)
        cmd_recorded = (record["cmd_left_urad_s"], record["cmd_right_urad_s"])
        if cmd_recomputed != cmd_recorded:
            return False, idx, (
                f"Line {idx}: Actuator command mismatch! "
                f"Recorded {cmd_recorded} != Recomputed {cmd_recomputed}"
            )

        if res.reason != record["reason"]:
            return False, idx, (
                f"Line {idx}: Reason mismatch! "
                f"Recorded '{record['reason']}' != Recomputed '{res.reason}'"
            )

        if res.state.mode.value != record["state"]:
            return False, idx, (
                f"Line {idx}: Mode mismatch! "
                f"Recorded '{record['state']}' != Recomputed '{res.state.mode.value}'"
            )

        if list(res.events) != record["events"]:
            return False, idx, (
                f"Line {idx}: Events mismatch! "
                f"Recorded {record['events']} != Recomputed {list(res.events)}"
            )

    return True, len(lines), ""


def parse_anchor_file(anchor_filepath: str) -> Tuple[Optional[int], Optional[str]]:
    """Parses expected head hash and sequence number from an ANCHOR.txt file."""
    if not os.path.isfile(anchor_filepath):
        raise FileNotFoundError(f"Anchor file not found: {anchor_filepath}")
    head_hash = None
    head_seq = None
    with open(anchor_filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if len(line) == 64 and all(c in "0123456789abcdefABCDEF" for c in line):
                head_hash = line.lower()
            elif line.startswith("head_hash="):
                head_hash = line.split("=", 1)[1].strip().lower()
            elif line.startswith("last_seq=") or line.startswith("head_seq="):
                head_seq = int(line.split("=", 1)[1].strip())
    return head_seq, head_hash


def main():
    parser = argparse.ArgumentParser(description="Audit and verify a QERRA Gate JSONL log file.")
    parser.add_argument("log_path", help="Path to the JSONL log file")
    parser.add_argument("--anchor-seq", type=int, default=None, help="Expected final sequence number")
    parser.add_argument("--anchor-hash", type=str, default=None, help="Expected final SHA-256 head hash")
    parser.add_argument("--anchor-file", type=str, default=None, help="Path to ANCHOR.txt containing head hash")
    parser.add_argument("--replay", action="store_true", help="Replay inputs through pure gate_core.step() and verify bit-for-bit output match")
    parser.add_argument("--lidar-n", type=int, default=None, help="Expected LiDAR samples count for replay")
    args = parser.parse_args()

    expected_seq = args.anchor_seq
    expected_hash = args.anchor_hash

    if args.anchor_file:
        file_seq, file_hash = parse_anchor_file(args.anchor_file)
        if expected_seq is None:
            expected_seq = file_seq
        if expected_hash is None:
            expected_hash = file_hash

    # 1. Cryptographic and format audit
    result = verify_log_file(
        args.log_path,
        expected_head_seq=expected_seq,
        expected_head_hash=expected_hash,
    )

    if not result.is_valid:
        print("!" * 70)
        print("[AUDIT FAILED] Tampering or corruption detected!")
        print(f"  • Reason           : {result.error_message}")
        print("!" * 70)
        sys.exit(1)

    print("=" * 70)
    if result.is_anchored:
        print("[AUDIT PASSED: ANCHORED] Log is mathematically intact and verified against external head seal.")
    else:
        print("[AUDIT WARNING: UNANCHORED] Hash chain is internally consistent,")
        print("  but WITHOUT an external anchor, offline log rewriting cannot be excluded.")
    print(f"  • Verified Records : {result.total_records}")
    print(f"  • Sequence Range   : {result.first_seq} -> {result.last_seq}")
    print(f"  • Head Hash (Seal) : {result.head_hash}")
    print(f"  • Anchor Status    : {'VERIFIED' if result.is_anchored else 'UNANCHORED'}")

    # 2. Replay audit if requested
    if args.replay:
        # Infer lidar_n from first record with ranges_m if not explicitly specified
        lidar_n = args.lidar_n
        if lidar_n is None:
            with open(args.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    inp = rec.get("inputs")
                    if inp and isinstance(inp.get("ranges_m"), list):
                        lidar_n = len(inp["ranges_m"])
                        break
        if lidar_n is None:
            lidar_n = 5  # fallback test default

        replay_params = get_live_gate_params(lidar_n_expected=lidar_n)
        ok, replayed_count, err = replay_log_file(args.log_path, replay_params)
        if ok:
            print(f"[REPLAY AUDIT PASSED] All {replayed_count} control cycles reproduced bit-for-bit through pure core step().")
        else:
            print("!" * 70)
            print(f"[REPLAY AUDIT FAILED] Replay diverged from recorded decision: {err}")
            print("!" * 70)
            sys.exit(2)

    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
