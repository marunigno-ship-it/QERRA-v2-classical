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
        # A single call, straight from a fresh CLEAR start, with no
        # sleep at all — escalation must never require a wait.
        stabilizer = StabilizedHSR()
        result = stabilizer.evaluate(make_input(0.50))
        self.assertEqual(result.status, HSRStatus.MONITOR)

    def test_brief_dip_does_not_immediately_deescalate(self):
        stabilizer = StabilizedHSR()
        stabilizer.evaluate(make_input(0.50))  # reach MONITOR

        # Below the 0.45 entry line, but still above the 0.35 exit
        # line — should NOT drop back to CLEAR yet.
        dip_reading = (MONITOR_EXIT_THRESHOLD + 0.45) / 2  # 0.40
        result = stabilizer.evaluate(make_input(dip_reading))
        self.assertEqual(result.status, HSRStatus.MONITOR)

    def test_sustained_calm_reading_eventually_deescalates(self):
        stabilizer = StabilizedHSR()
        stabilizer.evaluate(make_input(0.50))            # reach MONITOR
        stabilizer.evaluate(make_input(0.10))             # genuinely calm, starts the timer

        time.sleep(DWELL_SECONDS + 0.2)                   # wait past the dwell window

        result = stabilizer.evaluate(make_input(0.10))    # same calm reading, timer expired
        self.assertEqual(result.status, HSRStatus.CLEAR)

    def test_escalation_interrupts_pending_deescalation(self):
        stabilizer = StabilizedHSR()
        stabilizer.evaluate(make_input(0.50))             # reach MONITOR
        stabilizer.evaluate(make_input(0.10))              # starts a de-escalation timer

        # Before the dwell finishes, a real danger signal arrives —
        # must jump to CRITICAL immediately, no delay, no exceptions.
        result = stabilizer.evaluate(make_input(0.90))
        self.assertEqual(result.status, HSRStatus.CRITICAL)

    def test_deescalation_resets_timer_if_target_status_changes(self):
        """Bug #2 regression test:
        If the raw reading drifts between calmer levels (CRITICAL -> MONITOR -> CLEAR),
        the dwell timer must restart for CLEAR so it holds for a full DWELL_SECONDS.
        """
        simulated_time = 0.0

        def mock_clock():
            return simulated_time

        stabilizer = StabilizedHSR(clock=mock_clock)

        # 1. Start in CRITICAL at t = 0.0
        res = stabilizer.evaluate(make_input(0.90))
        self.assertEqual(res.status, HSRStatus.CRITICAL)

        # 2. At t = 1.0, raw drops to MONITOR. Stabilizer should hold CRITICAL while dwelling.
        simulated_time = 1.0
        res = stabilizer.evaluate(make_input(0.50))
        self.assertEqual(res.status, HSRStatus.CRITICAL)

        # 3. At t = 1.6 (0.6s later), raw drops to CLEAR. Stabilizer should still hold CRITICAL.
        simulated_time = 1.6
        res = stabilizer.evaluate(make_input(0.10))
        self.assertEqual(res.status, HSRStatus.CRITICAL)

        # 4. At t = 2.0 (1.0s from MONITOR, but ONLY 0.4s since CLEAR began):
        # System must NOT de-escalate to CLEAR prematurely.
        simulated_time = 2.0
        res = stabilizer.evaluate(make_input(0.10))
        self.assertNotEqual(
            res.status,
            HSRStatus.CLEAR,
            "Bug detected: Premature de-escalation! System reached CLEAR after only 0.4s of CLEAR."
        )

        # 5. At t = 2.7 (1.1s after CLEAR began at 1.6):
        # Now it has held CLEAR for the full 1.0s window, so it safely becomes CLEAR.
        simulated_time = 2.7
        res = stabilizer.evaluate(make_input(0.10))
        self.assertEqual(res.status, HSRStatus.CLEAR)


if __name__ == "__main__":
    unittest.main()
