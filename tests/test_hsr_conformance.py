# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Conformance tests between the two Layer 1B classifiers (standard library only, unittest):

  1. Floating-point evaluator:   hsr.qerra_hsr.evaluate_hsr()
  2. Integer-permille classifier: gate.hsr_telemetry.classify_hsr_telemetry()

What the sweep proves
---------------------
For every distress value on the 0.001 grid (permille 0..1000, float = permille / 1000.0),
both hazard states, persons_nearby_count 0..6, and both robot_task_interruptible values,
the two classifiers return the same reflex status.

What it does NOT prove
----------------------
- Behaviour between grid points (for example 0.4499999 or 0.4500001). No float-to-permille
  converter exists in production code; the permille wire form is the normative one.
- Behaviour on invalid input. The float path fails closed to CRITICAL; the wire path rejects
  the datagram (see test_invalid_input_asymmetry_is_pinned).

These tests use unittest (not pytest) on purpose: CI runs
`python -m unittest discover -s tests -p "test_*.py"` and does not install pytest.
"""
from __future__ import annotations

import json
import logging
import sys
import unittest
from pathlib import Path

# Ensure repository root is on sys.path when run directly from a terminal or PyCharm.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gate.hsr_telemetry import (  # noqa: E402
    DEFAULT_CRITICAL_THRESHOLD_PERMILLE,
    DEFAULT_MONITOR_THRESHOLD_PERMILLE,
    HSR_CRITICAL,
    HSR_MONITOR,
    ISOLATION_COUNT_THRESHOLD as WIRE_ISOLATION_COUNT_THRESHOLD,
    classify_hsr_telemetry,
    parse_hsr_telemetry,
)
from hsr import qerra_hsr  # noqa: E402
from hsr.qerra_hsr import HSRInput, evaluate_hsr  # noqa: E402

T_RX_US = 102_000


def _base_payload() -> dict:
    return {
        "obs_id": 1,
        "t_obs_us": 100_000,
        "t_emit_us": 101_000,
        "distress_permille": 500,
        "hazard_proximity": False,
        "persons_nearby_count": 2,
    }


def _parse(payload) -> object:
    raw = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
    return parse_hsr_telemetry(raw, t_rx_us=T_RX_US)


class TestFloatVsPermilleConformance(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        # evaluate_hsr() logs every call; 28,028 sweep calls would flood the CI log.
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls) -> None:
        logging.disable(logging.NOTSET)

    def test_threshold_constants_agree(self) -> None:
        """A threshold edited on one side only must fail here, not drift silently."""
        self.assertEqual(round(qerra_hsr.DISTRESS_MONITOR_THRESHOLD * 1000),
                         DEFAULT_MONITOR_THRESHOLD_PERMILLE)
        self.assertEqual(round(qerra_hsr.DISTRESS_CRITICAL_THRESHOLD * 1000),
                         DEFAULT_CRITICAL_THRESHOLD_PERMILLE)
        self.assertEqual(qerra_hsr.ISOLATION_COUNT_THRESHOLD, WIRE_ISOLATION_COUNT_THRESHOLD)

    def test_exhaustive_sweep_on_permille_grid(self) -> None:
        hazard_options = (False, True)
        interruptible_options = (True, False)
        person_counts = tuple(range(0, 7))  # covers the isolation boundary with margin on both sides

        evaluations_run = 0
        mismatches = []

        for permille in range(1001):
            distress_float = permille / 1000.0  # correctly rounded: equals the literal 0.45, 0.75, ...
            for hazard in hazard_options:
                for persons in person_counts:
                    derived = classify_hsr_telemetry(
                        distress_permille=permille,
                        hazard_proximity=hazard,
                        persons_nearby_count=persons,
                    )
                    for interruptible in interruptible_options:
                        result = evaluate_hsr(HSRInput(
                            distress_confidence=distress_float,
                            persons_nearby_count=persons,
                            hazard_proximity_flag=hazard,
                            robot_task_interruptible=interruptible,
                        ))
                        evaluations_run += 1
                        if result.status.value != derived:
                            mismatches.append(
                                (permille, hazard, persons, interruptible, result.status.value, derived)
                            )

        self.assertEqual(evaluations_run, 1001 * 2 * 7 * 2)
        self.assertEqual(
            mismatches[:10], [],
            "float (qerra_hsr) vs permille (hsr_telemetry) divergence; first 10 shown "
            "as (permille, hazard, persons, interruptible, float_status, permille_status)",
        )

    def test_invalid_input_asymmetry_is_pinned(self) -> None:
        """Decision pin, not an endorsement.

        Invalid input is handled differently by the two paths: the float evaluator fails
        closed to CRITICAL, while the wire parser rejects the datagram (a rejected datagram
        is treated as a lost one and is only counted). If the wire path is later changed to
        invalidate the stream on contradictory frames, update this test with that change.
        """
        result = evaluate_hsr(HSRInput(
            distress_confidence=float("nan"),
            persons_nearby_count=2,
            hazard_proximity_flag=False,
            robot_task_interruptible=True,
        ))
        self.assertEqual(result.status.value, HSR_CRITICAL)

        payload = _base_payload()
        payload["distress_permille"] = 1001
        with self.assertRaises(ValueError):
            _parse(payload)


class TestWireContractV04(unittest.TestCase):

    def test_valid_baseline_parses(self) -> None:
        pkt = _parse(_base_payload())
        self.assertEqual(pkt.state, HSR_MONITOR)
        self.assertIs(pkt.hazard_proximity, False)
        self.assertEqual(pkt.persons_nearby_count, 2)

    def test_missing_context_fields_are_rejected_with_field_name(self) -> None:
        for field in ("hazard_proximity", "persons_nearby_count"):
            with self.subTest(missing=field):
                payload = _base_payload()
                del payload[field]
                with self.assertRaisesRegex(ValueError, field):
                    _parse(payload)

    def test_missing_core_fields_are_rejected(self) -> None:
        for field in ("obs_id", "t_obs_us", "t_emit_us", "distress_permille"):
            with self.subTest(missing=field):
                payload = _base_payload()
                del payload[field]
                with self.assertRaisesRegex(ValueError, field):
                    _parse(payload)

    def test_rejected_payload_table(self) -> None:
        """Every one of these must raise ValueError (the receiver counts it as rejected)."""
        def with_(**changes) -> dict:
            payload = _base_payload()
            payload.update(changes)
            return payload

        cases = {
            "hazard int 1": with_(hazard_proximity=1),
            "hazard int 0": with_(hazard_proximity=0),
            "hazard null": with_(hazard_proximity=None),
            "hazard string": with_(hazard_proximity="false"),
            "persons bool": with_(persons_nearby_count=True),
            "persons negative": with_(persons_nearby_count=-1),
            "persons float 2.0": with_(persons_nearby_count=2.0),
            "persons null": with_(persons_nearby_count=None),
            "persons string": with_(persons_nearby_count="2"),
            "permille negative": with_(distress_permille=-1),
            "permille 1001": with_(distress_permille=1001),
            "permille float 500.0": with_(distress_permille=500.0),
            "permille string": with_(distress_permille="500"),
            "permille bool": with_(distress_permille=True),
            "obs_id negative": with_(obs_id=-1),
            "causal inversion": with_(t_emit_us=99_000),
            "future frame": with_(t_obs_us=T_RX_US + 1, t_emit_us=T_RX_US + 2),
            "declared state unknown": with_(state="PANIC"),
            "declared state mismatch": with_(distress_permille=900, state="CLEAR"),
            "json list": [1, 2, 3],
            "json scalar": 42,
            "not json": b"not json at all",
            "invalid utf-8": b"\xff\xfe\x00\x01",
            "empty datagram": b"",
        }
        for label, payload in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(ValueError):
                    _parse(payload)

    def test_declared_state_must_match_derived_state(self) -> None:
        payload = _base_payload()
        payload.update(distress_permille=900, state="CRITICAL")
        self.assertEqual(_parse(payload).state, HSR_CRITICAL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
