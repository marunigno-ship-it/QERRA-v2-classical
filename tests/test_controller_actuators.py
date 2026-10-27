# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Unit tests for Webots Supervisory Gate controller actuator boundaries.
Verifies independent fail-closed wheel clamping when motor drivers fault.
"""
import unittest

from controllers.tiago_supervisory_gate.tiago_supervisory_gate import zero_wheels


class MockMotor:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.velocity = 2.0  # Cruising before emergency stop

    def setVelocity(self, v: float):
        if self.fail:
            raise RuntimeError("Simulated motor driver communication fault")
        self.velocity = v


class TestControllerActuators(unittest.TestCase):
    def test_zero_wheels_independent_clamping_on_left_fault(self):
        """Rule: If left motor faults, right motor must STILL be commanded to 0.0 rad/s."""
        left = MockMotor(fail=True)
        right = MockMotor(fail=False)

        zero_wheels(left, right)

        self.assertEqual(right.velocity, 0.0, "Right wheel was abandoned when left wheel faulted!")

    def test_zero_wheels_independent_clamping_on_right_fault(self):
        """Rule: If right motor faults, left motor must STILL be commanded to 0.0 rad/s."""
        left = MockMotor(fail=False)
        right = MockMotor(fail=True)

        zero_wheels(left, right)

        self.assertEqual(left.velocity, 0.0, "Left wheel was abandoned when right wheel faulted!")

    def test_zero_wheels_handles_none_safely(self):
        """Rule: If motor handles are None, zero_wheels must not raise an unhandled exception."""
        zero_wheels(None, None)


if __name__ == "__main__":
    unittest.main()
