# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Tests for gate/gate_lidar.py (corridor filter & pipeline), including its interaction with gate_core.
Run from the repository root:
    python -m unittest tests.test_gate_lidar -v
"""
import logging
import math
import unittest

logging.getLogger("hsr.qerra_hsr").setLevel(logging.WARNING)

import gate.gate_lidar as gate_lidar_mod  # noqa: E402
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

    def test_blind_lidar_all_inf_must_trip_gate(self):
        """F1 defect: a completely blinded lidar (all +inf returns) must trip the gate, not pass as clear."""
        params = GateParams(
            lidar_n_expected=N, dt_us=32_000, t_watch_us=100_000, proposer_period_us=33_000,
            lidar_period_us=32_000, t_stale_us=96_000, wheel_radius_mm=98, a_design_mmps2=500, margin_mm=300,
            min_raw_lidar_returns=5)
        state, now, seq = initial_state(), 0, 0

        # Step through dwell (1.0 s = 32 ticks of 32_000 us) with clear corridor and healthy raw returns
        healthy_raw = [5.0] * N
        for _ in range(35):
            now += 32_000
            res = step(state, params, GateInputs(
                sim_time_us=now, proposal=Proposal(seq, now, 2_000_000, 2_000_000),
                ranges_m=self.f.apply(healthy_raw), lidar_stamp_us=now, raw_valid_points=N))
            seq += 1
            state = res.state

        # Operator reset to enter RUN mode
        now += 32_000
        res = step(state, params, GateInputs(
            sim_time_us=now, proposal=Proposal(seq, now, 2_000_000, 2_000_000),
            ranges_m=self.f.apply(healthy_raw), lidar_stamp_us=now, reset_source="operator",
            raw_valid_points=N))
        seq += 1
        state = res.state
        self.assertEqual(state.mode, Mode.RUN)

        # 1. Clear corridor with live sensor (e.g. walls outside corridor): MUST PASS
        wall_outside = scan_with_wall(1.0, lateral_min=0.6, lateral_max=1.0)
        filtered_clear = self.f.apply(wall_outside)
        raw_count_alive = sum(1 for r in wall_outside if math.isfinite(r))
        self.assertGreaterEqual(raw_count_alive, 5)
        self.assertTrue(all(math.isinf(r) for r in filtered_clear))

        now += 32_000
        res_clear = step(state, params, GateInputs(
            sim_time_us=now, proposal=Proposal(seq, now, 2_000_000, 2_000_000),
            ranges_m=filtered_clear, lidar_stamp_us=now, raw_valid_points=raw_count_alive))
        seq += 1
        state = res_clear.state
        self.assertEqual(res_clear.reason, Reason.PASS)

        # 2. Blind sensor (taped over): 0 finite returns in raw scan -> MUST TRIP TRIP_SENSOR_INVALID
        blind_raw = [math.inf] * N
        filtered_blind = self.f.apply(blind_raw)

        now += 32_000
        res_blind = step(state, params, GateInputs(
            sim_time_us=now, proposal=Proposal(seq, now, 2_000_000, 2_000_000),
            ranges_m=filtered_blind, lidar_stamp_us=now, raw_valid_points=0))

        self.assertEqual(res_blind.reason, Reason.TRIP_SENSOR_INVALID)
        self.assertEqual((res_blind.cmd_left_urad_s, res_blind.cmd_right_urad_s), (0, 0))
        self.assertFalse(res_blind.record["lidar_valid"])


class TestLidarPipelineFreshness(unittest.TestCase):
    """F2 defect reproduction: sensor pipeline must track freshness and trip when scan stalls."""

    def test_pipeline_frozen_sensor_goes_stale_and_trips(self):
        LidarPipeline = getattr(gate_lidar_mod, "LidarPipeline", None)
        self.assertIsNotNone(LidarPipeline)

        pipeline = LidarPipeline(corridor=CorridorFilter(N, FOV, HALF_WIDTH))
        params = GateParams(
            lidar_n_expected=N, dt_us=32_000, t_watch_us=100_000, proposer_period_us=33_000,
            lidar_period_us=32_000, t_stale_us=96_000, wheel_radius_mm=98, a_design_mmps2=500, margin_mm=300
        )
        state, now, seq = initial_state(), 0, 0
        raw_scan = [5.0] * N

        for _ in range(35):
            now += 32_000
            filtered, stamp_us, valid_pts = pipeline.process(raw_scan, now)
            res = step(state, params, GateInputs(
                sim_time_us=now, proposal=Proposal(seq, now, 2_000_000, 2_000_000),
                ranges_m=filtered, lidar_stamp_us=stamp_us, raw_valid_points=valid_pts
            ))
            seq += 1
            state = res.state

        now += 32_000
        filtered, stamp_us, valid_pts = pipeline.process(raw_scan, now)
        res = step(state, params, GateInputs(
            sim_time_us=now, proposal=Proposal(seq, now, 2_000_000, 2_000_000),
            ranges_m=filtered, lidar_stamp_us=stamp_us, reset_source="operator", raw_valid_points=valid_pts
        ))
        seq += 1
        state = res.state
        self.assertEqual(state.mode, Mode.RUN)

        stalled_reasons = []
        for _ in range(5):
            now += 32_000
            filtered, stamp_us, valid_pts = pipeline.process(raw_scan, now, stalled=True)
            res = step(state, params, GateInputs(
                sim_time_us=now, proposal=Proposal(seq, now, 2_000_000, 2_000_000),
                ranges_m=filtered, lidar_stamp_us=stamp_us, raw_valid_points=valid_pts
            ))
            seq += 1
            state = res.state
            stalled_reasons.append(res.reason)

        self.assertIn(Reason.TRIP_SENSOR_INVALID, stalled_reasons)
        self.assertEqual(state.mode, Mode.TRIPPED)


class TestLidarRangeBoundsREP117(unittest.TestCase):
    """Phase 3B (RED): Tests REP-117 range_min blind-zone and range_max validity enforcement."""

    def test_forward_corridor_below_range_min_trips_sensor_invalid(self):
        """A forward-corridor beam reading 0 < r < range_min must fail closed as NaN -> TRIP_SENSOR_INVALID."""
        corridor = CorridorFilter(N, FOV, HALF_WIDTH)
        pipeline = gate_lidar_mod.LidarPipeline(corridor=corridor)
        params = GateParams(
            lidar_n_expected=N, dt_us=32_000, t_watch_us=100_000, proposer_period_us=33_000,
            lidar_period_us=32_000, t_stale_us=96_000, wheel_radius_mm=98, a_design_mmps2=500, margin_mm=300
        )

        # Center beam reads 0.02 m, below range_min=0.05 m
        raw_scan = [3.0] * N
        raw_scan[N // 2] = 0.02

        filtered, stamp_us, valid_pts = pipeline.process(
            raw_scan, 100_000, range_min=0.05, range_max=5.6
        )
        self.assertTrue(math.isnan(filtered[N // 2]), "Forward below-min return must convert to NaN")
        self.assertEqual(valid_pts, N - 1, "Below-min beam must not count toward raw_valid_points")

        res = step(initial_state(), params, GateInputs(
            sim_time_us=100_000, proposal=Proposal(1, 100_000, 2_000_000, 2_000_000),
            ranges_m=filtered, lidar_stamp_us=stamp_us, raw_valid_points=valid_pts
        ))
        self.assertEqual(res.reason, Reason.TRIP_SENSOR_INVALID)

    def test_lateral_below_range_min_outside_corridor_does_not_nuisance_trip(self):
        """A lateral reading below range_min outside the swept corridor is masked to +inf (no trip)."""
        corridor = CorridorFilter(N, FOV, HALF_WIDTH)
        pipeline = gate_lidar_mod.LidarPipeline(corridor=corridor)

        # Index 0 is at -120 deg (rear-lateral, outside forward corridor)
        raw_scan = [3.0] * N
        raw_scan[0] = 0.02

        filtered, _, valid_pts = pipeline.process(
            raw_scan, 100_000, range_min=0.05, range_max=5.6
        )
        self.assertTrue(math.isinf(filtered[0]), "Rear-lateral < range_min must mask to +inf without NaN")
        self.assertEqual(valid_pts, N - 1)

    def test_above_range_max_excluded_from_liveness_and_masked_inf(self):
        """Readings strictly > range_max are treated as +inf and excluded from raw_valid_points."""
        corridor = CorridorFilter(N, FOV, HALF_WIDTH)
        pipeline = gate_lidar_mod.LidarPipeline(corridor=corridor)
        params = GateParams(
            lidar_n_expected=N, dt_us=32_000, t_watch_us=100_000, proposer_period_us=33_000,
            lidar_period_us=32_000, t_stale_us=96_000, wheel_radius_mm=98, a_design_mmps2=500, margin_mm=300,
            min_raw_lidar_returns=5
        )

        # Broken driver sends 999.0 across all beams when range_max is 5.6
        raw_scan = [999.0] * N
        filtered, stamp_us, valid_pts = pipeline.process(
            raw_scan, 100_000, range_min=0.05, range_max=5.6
        )
        self.assertEqual(valid_pts, 0, "Above-range_max values must not count as valid sensor returns")
        self.assertTrue(all(math.isinf(r) for r in filtered))

        res = step(initial_state(), params, GateInputs(
            sim_time_us=100_000, proposal=Proposal(1, 100_000, 2_000_000, 2_000_000),
            ranges_m=filtered, lidar_stamp_us=stamp_us, raw_valid_points=valid_pts
        ))
        self.assertEqual(res.reason, Reason.TRIP_SENSOR_INVALID)

    def test_boundary_values_equal_to_range_min_and_range_max_accepted(self):
        """Readings equal to range_min or range_max are strictly inside [range_min, range_max]."""
        corridor = CorridorFilter(N, FOV, HALF_WIDTH)
        pipeline = gate_lidar_mod.LidarPipeline(corridor=corridor)

        raw_scan = [5.6] * N
        raw_scan[N // 2] = 0.05

        filtered, _, valid_pts = pipeline.process(
            raw_scan, 100_000, range_min=0.05, range_max=5.6
        )
        self.assertEqual(filtered[N // 2], 0.05)
        self.assertEqual(valid_pts, N)


if __name__ == "__main__":
    unittest.main()
