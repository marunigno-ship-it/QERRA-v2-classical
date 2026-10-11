# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Marussa Metocharaki
"""
Tests for gate/gate_lidar.py (corridor filter), including its interaction with gate_core.
Run from the repository root:
    python -m unittest tests.test_gate_lidar -v
"""
import logging
import math
import unittest

logging.getLogger("hsr.qerra_hsr").setLevel(logging.WARNING)

from gate.gate_core import GateInputs, GateParams, Mode, Proposal, Reason, initial_state, step  # noqa: E402
from gate.gate_lidar import CorridorFilter  # noqa: E402

N = 667
FOV = 4.18            # about 240 degrees
HALF_WIDTH = 0.32


def ray(i, n=N, fov=FOV):
    return (i / (n - 1) - 0.5) * fov


def scan_with_wall(forward_m, lateral_min=-1.0, lateral_max=1.0):
    """Synthetic scan: a flat wall `forward_m` ahead, spanning lateral_min..lateral_max metres."""
    out = []
    for i in range(N):
        th = ray(i)
        c = math.cos(th)
        if c <= 1e-9:
            out.append(math.inf)
            continue
        r = forward_m / c
        lateral = r * math.sin(th)
        out.append(r if lateral_min <= lateral <= lateral_max else math.inf)
    return out


class TestCorridorFilter(unittest.TestCase):
    def setUp(self):
        self.f = CorridorFilter(N, FOV, HALF_WIDTH)

    def test_output_has_same_length(self):
        out = self.f.apply([5.0] * N)
        self.assertEqual(len(out), N)

    def test_wall_in_front_is_kept_in_corridor_only(self):
        out = self.f.apply(scan_with_wall(1.0))
        kept = [(i, r) for i, r in enumerate(out) if math.isfinite(r)]
        self.assertTrue(kept)
        for i, r in kept:
            self.assertLessEqual(abs(r * math.sin(ray(i))), HALF_WIDTH + 1e-9)
        # nothing outside the corridor survives
        self.assertTrue(all(math.isinf(r) for i, r in enumerate(out)
                            if abs(1.0 * math.tan(ray(i))) > HALF_WIDTH + 0.02))

    def test_wall_beside_the_robot_is_ignored(self):
        # wall 1 m ahead but only at lateral 0.6..1.0 m, outside the 0.32 m corridor
        out = self.f.apply(scan_with_wall(1.0, lateral_min=0.6, lateral_max=1.0))
        self.assertTrue(all(math.isinf(r) for r in out))

    def test_samples_behind_the_sensor_axis_are_ignored(self):
        f = CorridorFilter(N, 2 * math.pi, HALF_WIDTH)       # 360 degrees: half the samples point backwards
        out = f.apply([0.5] * N)
        for i, r in enumerate(out):
            if math.cos((i / (N - 1) - 0.5) * 2 * math.pi) <= 1e-9:
                self.assertTrue(math.isinf(r), i)

    def test_invalid_values_pass_through_unchanged(self):
        bad = [math.nan, -1.0, 0.0, -math.inf, "3", None, True]
        for b in bad:
            with self.subTest(value=repr(b)):
                scan = [5.0] * N
                scan[N // 2 + 50] = b                         # off-centre: would be filtered if it were valid
                out = self.f.apply(scan)
                got = out[N // 2 + 50]
                if isinstance(b, float) and math.isnan(b):
                    self.assertTrue(math.isnan(got))
                else:
                    self.assertEqual(got, b)
                    self.assertIs(type(got), type(b))

    def test_wrong_length_or_missing_returns_none(self):
        self.assertIsNone(self.f.apply(None))
        self.assertIsNone(self.f.apply([1.0] * (N - 1)))
        self.assertIsNone(self.f.apply(5))

    def test_constructor_validation(self):
        for args in [(1, FOV, 0.3), (N, 0.0, 0.3), (N, FOV, 0.0), (N, math.nan, 0.3),
                     (N, FOV, math.inf), (True, FOV, 0.3), (N, 7.0, 0.3)]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    CorridorFilter(*args)

    def test_filter_cannot_hide_a_nan_from_the_gate(self):
        """End to end: a NaN anywhere in the raw scan must still trip the gate."""
        params = GateParams(
            lidar_n_expected=N, dt_us=32_000, t_watch_us=100_000, proposer_period_us=33_000,
            lidar_period_us=32_000, t_stale_us=96_000, wheel_radius_mm=98, a_design_mmps2=500, margin_mm=300)
        state, now, seq = initial_state(), 0, 0
        raw = [5.0] * N
        raw[10] = math.nan                                    # far off-axis, outside the corridor
        res = None
        for _ in range(5):
            now += 32_000
            res = step(state, params, GateInputs(
                sim_time_us=now, proposal=Proposal(seq, now, 2_000_000, 2_000_000),
                ranges_m=self.f.apply(raw), lidar_stamp_us=now))
            seq += 1
            state = res.state
        self.assertEqual(res.reason, Reason.TRIP_SENSOR_INVALID)
        self.assertEqual((res.cmd_left_urad_s, res.cmd_right_urad_s), (0, 0))

    def test_obstacle_beside_centre_line_is_seen_by_corridor_but_not_by_narrow_cone(self):
        """The reason this module exists: an obstacle 0.2 m off-centre at 0.5 m ahead."""
        scan = scan_with_wall(0.5, lateral_min=0.15, lateral_max=0.25)
        filtered = self.f.apply(scan)
        self.assertTrue(any(math.isfinite(r) for r in filtered))          # corridor sees it
        mid, span = N // 2, N // 30                                       # the old +-8 degree cone
        old_cone = [scan[mid - span + i * (2 * span // 4)] for i in range(5)]
        self.assertTrue(all(math.isinf(r) for r in old_cone))             # old cone missed it


if __name__ == "__main__":
    unittest.main()
