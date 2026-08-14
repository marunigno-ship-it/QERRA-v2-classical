"""
QERRA Human Safety Response Layer — hsr/test_hsr_cases.py
Regression test suite v0.1

12 deterministic test cases covering:
- All three vectors individually
- The combined distress + isolation condition
- Boundary threshold values
- robot_task_interruptible contract
- Multiple vectors active simultaneously

All tests must pass before any commit.
Run with: python -m pytest hsr/test_hsr_cases.py -v
      or: python -m unittest hsr.test_hsr_cases -v
"""

import unittest
from hsr.qerra_hsr import (
    HSRInput,
    HSRStatus,
    HSRResult,
    evaluate_hsr,
    DISTRESS_CRITICAL_THRESHOLD,
    DISTRESS_MONITOR_THRESHOLD,
    ISOLATION_COUNT_THRESHOLD,
)


class TestHSRClear(unittest.TestCase):
    """Cases that should produce CLEAR — no safety signals."""

    def test_clear_no_signals(self):
        """All signals at baseline — no concern detected."""
        inp = HSRInput(
            distress_confidence=0.10,
            persons_nearby_count=5,
            hazard_proximity_flag=False,
            robot_task_interruptible=True,
        )
        res = evaluate_hsr(inp)
        self.assertEqual(res.status, HSRStatus.CLEAR)
        self.assertEqual(res.vectors_activated, [])
        self.assertIn("No safety signals detected", res.reasoning)

    def test_clear_just_below_monitor_threshold(self):
        """distress_confidence just below MONITOR threshold — must stay CLEAR.
        Protects against threshold boundary drift."""
        inp = HSRInput(
            distress_confidence=DISTRESS_MONITOR_THRESHOLD - 0.01,
            persons_nearby_count=0,
            hazard_proximity_flag=False,
            robot_task_interruptible=True,
        )
        res = evaluate_hsr(inp)
        self.assertEqual(res.status, HSRStatus.CLEAR)
        self.assertEqual(res.vectors_activated, [])


class TestHSRMonitor(unittest.TestCase):
    """Cases that should produce MONITOR — elevated but not critical."""

    def test_monitor_mild_distress_with_people_nearby(self):
        """Mild distress signal with people present → MONITOR.
        No vectors_activated because distress is below CRITICAL and person is not isolated.
        Status is MONITOR because distress_confidence >= DISTRESS_MONITOR_THRESHOLD."""
        inp = HSRInput(
            distress_confidence=0.55,
            persons_nearby_count=3,
            hazard_proximity_flag=False,
            robot_task_interruptible=True,
        )
        res = evaluate_hsr(inp)
        self.assertEqual(res.status, HSRStatus.MONITOR)
        # immediate_physical_distress does NOT activate at MONITOR level with people present
        self.assertNotIn("immediate_physical_distress", res.vectors_activated)
        self.assertNotIn("human_isolation", res.vectors_activated)

    def test_monitor_at_exact_monitor_threshold(self):
        """distress_confidence exactly at MONITOR threshold — must be MONITOR, not CLEAR.
        Boundary condition test."""
        inp = HSRInput(
            distress_confidence=DISTRESS_MONITOR_THRESHOLD,
            persons_nearby_count=4,
            hazard_proximity_flag=False,
            robot_task_interruptible=True,
        )
        res = evaluate_hsr(inp)
        self.assertEqual(res.status, HSRStatus.MONITOR)


class TestHSRCritical(unittest.TestCase):
    """Cases that should produce CRITICAL — immediate response required."""

    def test_critical_high_distress_alone(self):
        """High distress_confidence alone triggers CRITICAL via V01.
        People present — isolation does not apply, but distress is severe."""
        inp = HSRInput(
            distress_confidence=0.82,
            persons_nearby_count=4,
            hazard_proximity_flag=False,
            robot_task_interruptible=True,
        )
        res = evaluate_hsr(inp)
        self.assertEqual(res.status, HSRStatus.CRITICAL)
        self.assertIn("immediate_physical_distress", res.vectors_activated)
        self.assertNotIn("human_isolation", res.vectors_activated)

    def test_critical_at_exact_critical_threshold(self):
        """distress_confidence exactly at CRITICAL threshold — must fire CRITICAL.
        Boundary condition test."""
        inp = HSRInput(
            distress_confidence=DISTRESS_CRITICAL_THRESHOLD,
            persons_nearby_count=5,
            hazard_proximity_flag=False,
            robot_task_interruptible=True,
        )
        res = evaluate_hsr(inp)
        self.assertEqual(res.status, HSRStatus.CRITICAL)
        self.assertIn("immediate_physical_distress", res.vectors_activated)

    def test_critical_combined_distress_and_isolation(self):
        """THE COMBINED CONDITION: moderate distress + person isolated → CRITICAL.
        This is the most important combined rule — must be tested explicitly.
        distress_confidence is below CRITICAL threshold but person is alone."""
        inp = HSRInput(
            distress_confidence=0.60,
            persons_nearby_count=0,
            hazard_proximity_flag=False,
            robot_task_interruptible=True,
        )
        res = evaluate_hsr(inp)
        self.assertEqual(res.status, HSRStatus.CRITICAL)
        self.assertIn("immediate_physical_distress", res.vectors_activated)
        self.assertIn("human_isolation", res.vectors_activated)

    def test_critical_environmental_hazard_only(self):
        """Environmental hazard alone triggers CRITICAL via V03.
        No distress signal present — V03 is an independent trigger."""
        inp = HSRInput(
            distress_confidence=0.10,
            persons_nearby_count=5,
            hazard_proximity_flag=True,
            robot_task_interruptible=True,
        )
        res = evaluate_hsr(inp)
        self.assertEqual(res.status, HSRStatus.CRITICAL)
        self.assertIn("environmental_hazard_proximity", res.vectors_activated)
        self.assertNotIn("immediate_physical_distress", res.vectors_activated)

    def test_critical_all_vectors_active(self):
        """All three vectors active simultaneously.
        High distress + isolated + hazard + task not interruptible.
        robot_task_interruptible=False must NOT prevent CRITICAL."""
        inp = HSRInput(
            distress_confidence=0.80,
            persons_nearby_count=1,
            hazard_proximity_flag=True,
            robot_task_interruptible=False,
        )
        res = evaluate_hsr(inp)
        self.assertEqual(res.status, HSRStatus.CRITICAL)
        self.assertIn("immediate_physical_distress", res.vectors_activated)
        self.assertIn("human_isolation", res.vectors_activated)
        self.assertIn("environmental_hazard_proximity", res.vectors_activated)


class TestHSRContractGuarantees(unittest.TestCase):
    """Tests that enforce architectural contracts from the design document."""

    def test_interruptible_false_does_not_prevent_critical(self):
        """robot_task_interruptible affects HOW the robot responds, never WHETHER.
        CRITICAL must fire regardless of this flag."""
        inp_interruptible = HSRInput(0.82, 0, False, True)
        inp_not_interruptible = HSRInput(0.82, 0, False, False)
        res_true = evaluate_hsr(inp_interruptible)
        res_false = evaluate_hsr(inp_not_interruptible)
        self.assertEqual(res_true.status, HSRStatus.CRITICAL)
        self.assertEqual(res_false.status, HSRStatus.CRITICAL)
        self.assertEqual(res_true.vectors_activated, res_false.vectors_activated)

    def test_result_always_has_reasoning(self):
        """Every result must have a non-empty reasoning string — even CLEAR.
        Ensures logs are always auditable."""
        for confidence, count, hazard in [
            (0.10, 5, False),   # CLEAR
            (0.55, 3, False),   # MONITOR
            (0.82, 0, True),    # CRITICAL
        ]:
            inp = HSRInput(confidence, count, hazard, True)
            res = evaluate_hsr(inp)
            self.assertIsInstance(res.reasoning, str)
            self.assertGreater(len(res.reasoning), 0,
                msg=f"Empty reasoning for status={res.status}")

    def test_result_version_is_correct(self):
        """Version string must be 0.1 — guards against accidental version drift."""
        inp = HSRInput(0.10, 3, False, True)
        res = evaluate_hsr(inp)
        self.assertEqual(res.version, "0.1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
