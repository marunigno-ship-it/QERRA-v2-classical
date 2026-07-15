# =====================================================
# test_bridge_hysteresis.py
# Confirms the hysteresis stabilizer, when passed into
# _call_local_engine(), actually gets used — and that its memory
# persists correctly across separate calls, exactly as it would
# across separate goals handled by one QerraActionServer.
#
# Does NOT require rclpy or a running ROS 2 environment.
#
# Loads the SentenceTransformer model on import (via ethical_core),
# same as every other test in this repo — first run may take a
# few seconds.
#
# Run with:
#   python -m unittest test_bridge_hysteresis -v
# =====================================================

import unittest

from hsr.hysteresis_wrapper import StabilizedHSR
from ros2_bridge import _call_local_engine


def hsr_signals(confidence):
    return {
        "distress_confidence": confidence,
        "persons_nearby_count": 3,
        "hazard_proximity_flag": False,
        "robot_task_interruptible": True,
    }


SAFE_TEXT = "The robot navigated successfully to the supply room."
CRITICAL_EXPLANATION = "critical physical safety concern (QERRA-HSR)"


class TestBridgeHysteresisIntegration(unittest.TestCase):

    def test_without_stabilizer_behavior_is_unchanged(self):
        # No stabilizer passed — must behave exactly as before this
        # change existed. 0.50 is MONITOR-level, not CRITICAL, so
        # SEMEV-12 should run normally (proven by "vector_scores"
        # being present — only the SEMEV-12 result dict has that key).
        result = _call_local_engine(SAFE_TEXT, hsr_signals=hsr_signals(0.50))
        self.assertIn("vector_scores", result)

    def test_with_stabilizer_escalation_is_instant(self):
        stabilizer = StabilizedHSR()
        result = _call_local_engine(
            SAFE_TEXT, hsr_signals=hsr_signals(0.90), stabilizer=stabilizer
        )
        self.assertEqual(result["score_explanation"], CRITICAL_EXPLANATION)

    def test_stabilizer_memory_persists_across_calls(self):
        # ONE stabilizer, reused across two separate calls — exactly
        # how one QerraActionServer reuses it across two goals.
        stabilizer = StabilizedHSR()

        # Call 1: a genuine hazard reading — escalates instantly.
        result1 = _call_local_engine(
            SAFE_TEXT, hsr_signals=hsr_signals(0.90), stabilizer=stabilizer
        )
        self.assertEqual(result1["score_explanation"], CRITICAL_EXPLANATION)

        # Call 2: immediately after, a reading that looks totally calm.
        # Without memory, this alone would look completely safe. WITH
        # the stabilizer, it must not trust that dip yet — no real
        # time has passed, so it should still report CRITICAL.
        result2 = _call_local_engine(
            SAFE_TEXT, hsr_signals=hsr_signals(0.10), stabilizer=stabilizer
        )
        self.assertEqual(result2["score_explanation"], CRITICAL_EXPLANATION)


if __name__ == "__main__":
    unittest.main()
