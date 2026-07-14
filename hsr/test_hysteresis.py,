# =====================================================
# test_hysteresis.py
# QERRA-HSR — Regression tests for the hysteresis wrapper
#
# Tests StabilizedHSR only. Does not modify or re-test
# hsr/qerra_hsr.py — that file's own 12 tests stay separate,
# untouched, in hsr/test_hsr_cases.py.
#
# One test genuinely waits out the dwell period with a real
# time.sleep(), so this file takes a couple of seconds to run —
# that's expected, not a bug.
#
# Run with:
#   python -m unittest hsr.test_hysteresis -v
# =====================================================

import time
import unittest

from hsr.qerra_hsr import HSRInput, HSRStatus
from hsr.hysteresis_wrapper import StabilizedHSR, DWELL_SECONDS, MONITOR_EXIT_THRESHOLD


def make_input(confidence):
    """Shortcut: a distress-only reading, everything else at baseline."""
    return HSRInput(
        distress_confidence=confidence,
        persons_nearby_count=3,
        hazard_proximity_flag=False,
        robot_task_interruptible=True,
    )


class TestStabilizedHSR(unittest.TestCase):

    def test_fresh_instance_starts_clear(self):
        stabilizer = StabilizedHSR()
        result = stabilizer.evaluate(make_input(0.10))
        self.assertEqual(result.status, HSRStatus.CLEAR)

    def test_escalation_is_instant(self):
        stabilizer = StabilizedHSR()
        result = stabilizer.evaluate(make_input(0.50))
        self.assertEqual(result.status, HSRStatus.MONITOR)

    def test_brief_dip_does_not_immediately_deescalate(self):
        stabilizer = StabilizedHSR()
        stabilizer.evaluate(make_input(0.50))  # reach MONITOR

        dip_reading = (MONITOR_EXIT_THRESHOLD + 0.45) / 2  # 0.40
        result = stabilizer.evaluate(make_input(dip_reading))
        self.assertEqual(result.status, HSRStatus.MONITOR)

    def test_sustained_calm_reading_eventually_deescalates(self):
        stabilizer = StabilizedHSR()
        stabilizer.evaluate(make_input(0.50))
        stabilizer.evaluate(make_input(0.10))

        time.sleep(DWELL_SECONDS + 0.2)

        result = stabilizer.evaluate(make_input(0.10))
        self.assertEqual(result.status, HSRStatus.CLEAR)

    def test_escalation_interrupts_pending_deescalation(self):
        stabilizer = StabilizedHSR()
        stabilizer.evaluate(make_input(0.50))
        stabilizer.evaluate(make_input(0.10))

        result = stabilizer.evaluate(make_input(0.90))
        self.assertEqual(result.status, HSRStatus.CRITICAL)


if __name__ == "__main__":
    unittest.main()
