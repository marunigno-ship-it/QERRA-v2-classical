# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
Unit tests for gate/gate_log.py and verify_log.py (SAFETY_CONCEPT.md v0.1).
Covers: T-13 (Log mutation tests: edits, deletion, insertion, reorder, CRLF, truncation),
        T-14 (Log write failure trip & latch),
        F5 (obstacle_breach persistence, fsync crash resilience, deterministic replay inputs).
Standard library only.
"""
import json
import os
import tempfile
import unittest

from gate.gate_core import (
    GateInputs, GateParams, Mode, Reason, initial_state, step,
)
from gate.gate_log import GateLogger
from verify_log import verify_log_file


class TestGateLogMutation(unittest.TestCase):
    """T-13: Mutation tests on audit log. Proves any tampering is detected."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.temp_dir.name, "test_audit.jsonl")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _generate_clean_log(self, count: int = 5) -> tuple[int, str]:
        """Generates a valid, clean log with `count` records."""
        final_seq = 0
        final_hash = ""
        with GateLogger(self.log_path, run_id="RUN_TEST_001") as logger:
            for i in range(count):
                fake_record = {
                    "sim_time_us": 1_000_000 + i * 32_000,
                    "state": "RUN",
                    "reason": "PASS",
                    "events": [],
                    "proposal_seq": i,
                    "proposal_age_us": 10_000,
                    "lidar_valid": True,
                    "lidar_min_mm": 2500,
                    "d_stop_mm": 350,
                    "obstacle_breach": False,
                    "hsr_status": "CLEAR",
                    "cmd_left_urad_s": 2_000_000,
                    "cmd_right_urad_s": 2_000_000,
                }
                _, final_hash = logger.append(fake_record, wall_ns=1000 + i * 100)
                final_seq = i
        return final_seq, final_hash

    def test_clean_log_verifies_successfully(self):
        head_seq, head_hash = self._generate_clean_log(5)
        res = verify_log_file(self.log_path, expected_head_seq=head_seq, expected_head_hash=head_hash)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.total_records, 5)
        self.assertEqual(res.head_hash, head_hash)

    def test_mutation_field_edit_detected(self):
        self._generate_clean_log(5)
        with open(self.log_path, "rb") as f:
            lines = f.readlines()

        # Mutate line 2: change cmd_left_urad_s
        lines[2] = lines[2].replace(b"2000000", b"3000000", 1)

        with open(self.log_path, "wb") as f:
            f.writelines(lines)

        res = verify_log_file(self.log_path)
        self.assertFalse(res.is_valid)
        self.assertIn("Tampering detected", res.error_message)

    def test_mutation_line_deletion_detected(self):
        self._generate_clean_log(5)
        with open(self.log_path, "rb") as f:
            lines = f.readlines()

        # Delete line 2 (seq=2)
        del lines[2]

        with open(self.log_path, "wb") as f:
            f.writelines(lines)

        res = verify_log_file(self.log_path)
        self.assertFalse(res.is_valid)
        self.assertIn("Sequence mismatch", res.error_message)

    def test_mutation_line_insertion_detected(self):
        self._generate_clean_log(5)
        with open(self.log_path, "rb") as f:
            lines = f.readlines()

        # Duplicate line 1 (insert extra line)
        lines.insert(2, lines[1])

        with open(self.log_path, "wb") as f:
            f.writelines(lines)

        res = verify_log_file(self.log_path)
        self.assertFalse(res.is_valid)
        self.assertIn("Sequence mismatch", res.error_message)

    def test_mutation_line_reorder_detected(self):
        self._generate_clean_log(5)
        with open(self.log_path, "rb") as f:
            lines = f.readlines()

        # Swap line 1 and line 2
        lines[1], lines[2] = lines[2], lines[1]

        with open(self.log_path, "wb") as f:
            f.writelines(lines)

        res = verify_log_file(self.log_path)
        self.assertFalse(res.is_valid)
        self.assertIn("Sequence mismatch", res.error_message)

    def test_mutation_crlf_detected(self):
        self._generate_clean_log(5)
        with open(self.log_path, "rb") as f:
            content = f.read()

        # Convert LF to Windows CRLF (\r\n)
        content_crlf = content.replace(b"\n", b"\r\n")

        with open(self.log_path, "wb") as f:
            f.write(content_crlf)

        res = verify_log_file(self.log_path)
        self.assertFalse(res.is_valid)
        self.assertIn("CRLF", res.error_message)

    def test_truncation_detected_against_anchor(self):
        head_seq, head_hash = self._generate_clean_log(5)
        with open(self.log_path, "rb") as f:
            lines = f.readlines()

        # Cut off the last line (lines now 0..3 instead of 0..4)
        del lines[-1]

        with open(self.log_path, "wb") as f:
            f.writelines(lines)

        # Without anchor, remaining lines are internally valid
        res_no_anchor = verify_log_file(self.log_path)
        self.assertTrue(res_no_anchor.is_valid)

        # With anchor, truncation is caught immediately!
        res_anchored = verify_log_file(self.log_path, expected_head_seq=head_seq, expected_head_hash=head_hash)
        self.assertFalse(res_anchored.is_valid)
        self.assertIn("Truncation detected", res_anchored.error_message)

    def test_time_regression_detected(self):
        self._generate_clean_log(3)
        with open(self.log_path, "rb") as f:
            lines = f.readlines()

        # Mutate sim_time_us on line 1 to make it regress
        lines[1] = lines[1].replace(b"1032000", b"999000")

        with open(self.log_path, "wb") as f:
            f.writelines(lines)

        res = verify_log_file(self.log_path)
        self.assertFalse(res.is_valid)
        self.assertIn("Time anomaly", res.error_message)


class TestT14LogWriteFailure(unittest.TestCase):
    """T-14: Log write failure trips the gate and latches fail-closed."""

    def test_log_write_failure_trips_and_latches(self):
        params = GateParams(lidar_n_expected=5)
        state = initial_state()

        # Tick with log_write_failed=True
        inp = GateInputs(
            sim_time_us=1_000_000,
            ranges_m=[5.0] * 5,
            lidar_stamp_us=1_000_000,
            log_write_failed=True,
        )
        res = step(state, params, inp)

        self.assertEqual(res.reason, Reason.TRIP_LOG_FAILURE)
        self.assertEqual((res.cmd_left_urad_s, res.cmd_right_urad_s), (0, 0))
        self.assertEqual(res.state.mode, Mode.TRIPPED)


class TestF5RecorderDefects(unittest.TestCase):
    """F5 defect reproductions: missing obstacle_breach, missing fsync, missing inputs for replay."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.temp_dir.name, "test_f5_audit.jsonl")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_obstacle_breach_written_to_log(self):
        """F5 defect: obstacle_breach is documented in schema but gate_log.py omits it from disk."""
        with GateLogger(self.log_path, run_id="RUN_F5_BREACH") as logger:
            fake_record = {
                "sim_time_us": 1_000_000,
                "state": "TRIPPED",
                "reason": "TRIP_OBSTACLE",
                "events": [],
                "proposal_seq": 1,
                "proposal_age_us": 10_000,
                "lidar_valid": True,
                "lidar_min_mm": 250,
                "d_stop_mm": 350,
                "obstacle_breach": True,
                "hsr_status": None,
                "cmd_left_urad_s": 0,
                "cmd_right_urad_s": 0,
            }
            logger.append(fake_record, wall_ns=1000)

        with open(self.log_path, "r", encoding="utf-8") as f:
            line_data = json.loads(f.readline())

        # Fails on current code: obstacle_breach is missing
        self.assertIn("obstacle_breach", line_data, "F5 defect: obstacle_breach omitted by GateLogger.append")
        self.assertTrue(line_data["obstacle_breach"])

    def test_fsync_called_on_append(self):
        """F5 defect: append() flushes Python buffer but omits os.fsync, risking crash data loss."""
        fsync_called = []
        real_fsync = os.fsync
        try:
            def mock_fsync(fd):
                fsync_called.append(fd)

            os.fsync = mock_fsync
            with GateLogger(self.log_path, run_id="RUN_F5_FSYNC") as logger:
                fake_record = {
                    "sim_time_us": 1_000_000,
                    "state": "RUN",
                    "reason": "PASS",
                    "events": [],
                    "proposal_seq": 1,
                    "proposal_age_us": 10_000,
                    "lidar_valid": True,
                    "lidar_min_mm": 2500,
                    "d_stop_mm": 350,
                    "obstacle_breach": False,
                    "hsr_status": None,
                    "cmd_left_urad_s": 2_000_000,
                    "cmd_right_urad_s": 2_000_000,
                }
                logger.append(fake_record, wall_ns=1000)
                # Fails on current code: os.fsync was never called
                self.assertTrue(fsync_called, "F5 defect: os.fsync was never called after log write")
        finally:
            os.fsync = real_fsync

    def test_inputs_logged_for_deterministic_replay(self):
        """F5 defect: inputs are not logged, so offline replay cannot verify step()."""
        with GateLogger(self.log_path, run_id="RUN_F5_REPLAY") as logger:
            fake_record = {
                "sim_time_us": 1_000_000,
                "state": "RUN",
                "reason": "PASS",
                "events": [],
                "proposal_seq": 1,
                "proposal_age_us": 10_000,
                "lidar_valid": True,
                "lidar_min_mm": 2500,
                "d_stop_mm": 350,
                "obstacle_breach": False,
                "hsr_status": None,
                "cmd_left_urad_s": 2_000_000,
                "cmd_right_urad_s": 2_000_000,
                "inputs": {
                    "raw_valid_points": 500,
                    "lidar_stamp_us": 1_000_000,
                    "reset_source": None,
                    "log_write_failed": False,
                },
            }
            logger.append(fake_record, wall_ns=1000)

        with open(self.log_path, "r", encoding="utf-8") as f:
            line_data = json.loads(f.readline())

        # Fails on current code: inputs is omitted
        self.assertIn("inputs", line_data, "F5 defect: inputs omitted from log; cannot replay pure core")


if __name__ == "__main__":
    unittest.main()
