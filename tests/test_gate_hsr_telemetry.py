# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Unit tests for QERRA Layer 1B Asynchronous Telemetry Contract.
Verifies integer permille thresholds, schema validation, timestamp invariants,
and worst-severity batch reduction. Standard library only.
"""

from __future__ import annotations

import json
import unittest

from gate.hsr_telemetry import (
    HSR_CLEAR,
    HSR_MONITOR,
    HSR_CRITICAL,
    HSRTelemetryPacket,
    classify_hsr_telemetry,
    parse_hsr_telemetry,
    drain_worst_severity,
    is_perception_frozen,
)


class TestHSRTelemetryContract(unittest.TestCase):

    def test_permille_boundary_classification(self):
        """Verifies exact integer permille transitions matching hsr/qerra_hsr.py."""
        self.assertEqual(classify_hsr_telemetry(0), HSR_CLEAR)
        self.assertEqual(classify_hsr_telemetry(449), HSR_CLEAR)
        self.assertEqual(classify_hsr_telemetry(450), HSR_MONITOR)
        self.assertEqual(classify_hsr_telemetry(749), HSR_MONITOR)
        self.assertEqual(classify_hsr_telemetry(750), HSR_CRITICAL)
        self.assertEqual(classify_hsr_telemetry(1000), HSR_CRITICAL)

        with self.assertRaises(ValueError):
            classify_hsr_telemetry(-1)
        with self.assertRaises(ValueError):
            classify_hsr_telemetry(1001)
        with self.assertRaises(ValueError):
            classify_hsr_telemetry(True)  # type: ignore

    def test_compound_vector_escalation(self):
        """Verifies distress >= 450 combined with isolation (count <= 1) trips CRITICAL."""
        # Non-isolated (count >= 2) remains MONITOR at 450
        self.assertEqual(classify_hsr_telemetry(450, persons_nearby_count=2), HSR_MONITOR)
        self.assertEqual(classify_hsr_telemetry(450, persons_nearby_count=5), HSR_MONITOR)

        # Isolated (count <= 1) escalates MONITOR distress to CRITICAL
        self.assertEqual(classify_hsr_telemetry(450, persons_nearby_count=1), HSR_CRITICAL)
        self.assertEqual(classify_hsr_telemetry(450, persons_nearby_count=0), HSR_CRITICAL)

        # Low distress (< 450) with isolation does NOT trigger alarm fatigue
        self.assertEqual(classify_hsr_telemetry(400, persons_nearby_count=0), HSR_CLEAR)

    def test_hazard_proximity_flag(self):
        """Verifies environmental hazard proximity unconditionally forces CRITICAL."""
        self.assertEqual(classify_hsr_telemetry(0, hazard_proximity=True), HSR_CRITICAL)
        self.assertEqual(classify_hsr_telemetry(100, hazard_proximity=True), HSR_CRITICAL)

    def test_parse_valid_payload(self):
        """Verifies standard wire parsing and immutability of HSRTelemetryPacket."""
        payload = json.dumps({
            "obs_id": 42,
            "t_obs_us": 100_000,
            "t_emit_us": 105_000,
            "distress_permille": 750,
            "state": "CRITICAL",
            "hazard_proximity": False,
            "persons_nearby_count": 2,
        })
        pkt = parse_hsr_telemetry(payload, t_rx_us=110_000)
        self.assertEqual(pkt.obs_id, 42)
        self.assertEqual(pkt.t_obs_us, 100_000)
        self.assertEqual(pkt.t_emit_us, 105_000)
        self.assertEqual(pkt.t_rx_us, 110_000)
        self.assertEqual(pkt.distress_permille, 750)
        self.assertEqual(pkt.state, HSR_CRITICAL)
        self.assertEqual(pkt.severity(), 2)

    def test_parse_schema_rejections(self):
        """Verifies strict fail-closed rejection of missing or corrupted fields."""
        base = {"obs_id": 1, "t_obs_us": 100, "t_emit_us": 200, "distress_permille": 0}

        # Missing required field
        bad_missing = dict(base)
        del bad_missing["distress_permille"]
        with self.assertRaises(ValueError):
            parse_hsr_telemetry(json.dumps(bad_missing), t_rx_us=300)

        # Boolean in integer slot
        bad_bool = dict(base, obs_id=True)
        with self.assertRaises(ValueError):
            parse_hsr_telemetry(json.dumps(bad_bool), t_rx_us=300)

        # Float in integer slot
        bad_float = dict(base, distress_permille=750.5)
        with self.assertRaises(ValueError):
            parse_hsr_telemetry(json.dumps(bad_float), t_rx_us=300)

        # Declared state mismatch
        bad_state = dict(base, distress_permille=0, state="CRITICAL")
        with self.assertRaises(ValueError):
            parse_hsr_telemetry(json.dumps(bad_state), t_rx_us=300)

    def test_timestamp_causal_invariants(self):
        """Verifies rejection of inverted timestamps and future observations."""
        base = {"obs_id": 1, "t_obs_us": 1000, "t_emit_us": 2000, "distress_permille": 0}

        # Causal inversion: emission earlier than observation
        bad_emit = dict(base, t_emit_us=900)
        with self.assertRaises(ValueError):
            parse_hsr_telemetry(json.dumps(bad_emit), t_rx_us=3000)

        # Future frame: observation later than Gate receipt time
        with self.assertRaises(ValueError):
            parse_hsr_telemetry(json.dumps(base), t_rx_us=999)

    def test_worst_severity_drain_reduction(self):
        """Verifies that within a single tick batch, worst severity strictly dominates."""
        p_clear_early = HSRTelemetryPacket(1, 1000, 1100, 1500, 0, HSR_CLEAR)
        p_crit_mid = HSRTelemetryPacket(2, 1020, 1120, 1500, 800, HSR_CRITICAL)
        p_mon_late = HSRTelemetryPacket(3, 1040, 1140, 1500, 500, HSR_MONITOR)
        p_clear_latest = HSRTelemetryPacket(4, 1060, 1160, 1500, 0, HSR_CLEAR)

        batch = [p_clear_early, p_crit_mid, p_mon_late, p_clear_latest]
        winning = drain_worst_severity(batch)
        self.assertIsNotNone(winning)
        self.assertEqual(winning.obs_id, 2)
        self.assertEqual(winning.state, HSR_CRITICAL)

        # Empty batch returns None
        self.assertIsNone(drain_worst_severity([]))

    def test_freshest_tie_breaker(self):
        """Verifies that equal-severity ties are resolved by newest observation time."""
        p_crit_1 = HSRTelemetryPacket(10, 2000, 2100, 2500, 800, HSR_CRITICAL)
        p_crit_2 = HSRTelemetryPacket(11, 2050, 2150, 2500, 850, HSR_CRITICAL)

        winning = drain_worst_severity([p_crit_1, p_crit_2])
        self.assertIsNotNone(winning)
        self.assertEqual(winning.obs_id, 11)
        self.assertEqual(winning.t_obs_us, 2050)

    def test_frozen_frame_detector(self):
        """Verifies detection of static or regressing perception frame counts."""
        self.assertFalse(is_perception_frozen(current_obs_id=10, last_seen_obs_id=None))
        self.assertFalse(is_perception_frozen(current_obs_id=11, last_seen_obs_id=10))
        self.assertTrue(is_perception_frozen(current_obs_id=10, last_seen_obs_id=10))  # frozen
        self.assertTrue(is_perception_frozen(current_obs_id=9, last_seen_obs_id=10))   # replay/regression


if __name__ == "__main__":
    unittest.main()
