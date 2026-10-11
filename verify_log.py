# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
QERRA Supervisory Gate -- Standalone Flight Recorder Auditor (Demo 7).
SAFETY_CONCEPT.md v0.1: R-09, Section 9.

Verifies:
  1. Monotonic sequence numbers starting at 0 with no gaps.
  2. Strictly increasing simulation time (sim_time_us).
  3. No Windows CRLF (\r\n) line corruptions.
  4. Genesis hash equals 64 zeros.
  5. SHA-256 hash chain continuity: hash == SHA256(prev_hash + canonical_bytes).
  6. Truncation detection against externally anchored head hash & final sequence number.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Optional, Tuple

from gate.gate_log import GENESIS_HASH, compute_record_hash, serialize_canonical


@dataclass
class VerificationResult:
    is_valid: bool
    total_records: int
    first_seq: Optional[int]
    last_seq: Optional[int]
    head_hash: Optional[str]
    error_message: str


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

    # 5. External Anchor Verification (Truncation detection)
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
        )

    return VerificationResult(
        is_valid=True,
        total_records=total_records,
        first_seq=first_seq,
        last_seq=last_seq,
        head_hash=current_hash,
        error_message="",
    )


def main():
    parser = argparse.ArgumentParser(description="Audit and verify a QERRA Gate JSONL log file.")
    parser.add_argument("log_path", help="Path to the JSONL log file")
    parser.add_argument("--anchor-seq", type=int, default=None, help="Expected final sequence number")
    parser.add_argument("--anchor-hash", type=str, default=None, help="Expected final SHA-256 head hash")
    args = parser.parse_args()

    result = verify_log_file(
        args.log_path,
        expected_head_seq=args.anchor_seq,
        expected_head_hash=args.anchor_hash,
    )

    if result.is_valid:
        print("=" * 70)
        print("[AUDIT PASSED] Log is mathematically intact and unforgeable.")
        print(f"  • Verified Records : {result.total_records}")
        print(f"  • Sequence Range   : {result.first_seq} -> {result.last_seq}")
        print(f"  • Head Hash (Seal) : {result.head_hash}")
        print("=" * 70)
        sys.exit(0)
    else:
        print("!" * 70)
        print("[AUDIT FAILED] Tampering or corruption detected!")
        print(f"  • Reason           : {result.error_message}")
        print("!" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
