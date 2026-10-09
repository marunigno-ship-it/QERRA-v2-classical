# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
import unittest
from ros2_bridge import hybrid_evaluate

CALM_SIGNALS = {
    "distress_confidence": 0.10,
    "persons_nearby_count": 3,
    "hazard_proximity_flag": False,
    "robot_task_interruptible": True,
}

class TestBridgeFailClosed(unittest.TestCase):
    def test_none_signals_fails_closed(self):
        res, used_local = hybrid_evaluate("Safe routine patrol", hsr_signals=None)
        self.assertEqual(res.get("decision"), "modified")
        self.assertGreaterEqual(res.get("score", 0), 0.98)
        self.assertTrue(used_local)

    def test_empty_signals_fails_closed(self):
        res, used_local = hybrid_evaluate("Safe routine patrol", hsr_signals={})
        self.assertEqual(res.get("decision"), "modified")
        self.assertGreaterEqual(res.get("score", 0), 0.98)
        self.assertTrue(used_local)

    def test_valid_calm_signals_proceeds_to_deliberation(self):
        res, _ = hybrid_evaluate("Safe routine patrol", hsr_signals=CALM_SIGNALS)
        self.assertEqual(res.get("decision"), "safe")
        self.assertLess(res.get("score", 1.0), 0.50)

if __name__ == "__main__":
    unittest.main()
