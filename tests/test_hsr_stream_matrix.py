# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Pure-function scenario matrix tests for the Layer 1B perception stream monitor.
Tests step_hsr_stream() in gate.hsr_telemetry across edge cases identified in Gap 4.1:
  - Interleaved asynchronous producers
  - Backward timestamps with advancing frame counters
  - Identical timestamps with advancing frame counters (time stagnation)
  - Stuttering producer (n, n, n+1, n+1)
  - Mid-dwell distress resets (MONITOR / CRITICAL resetting streak and elapsed timer)
  - Intra-batch counter regressions
Standard library and pure gate imports only. Executes on Windows without ROS 2.
"""
from __future__ import annotations

import unittest

from gate.hsr_telemetry import (
    HSR_CLEAR,
    HSR_CRITICAL,
    HSR_MONITOR,
    HSRStreamState,
    HSRTelemetryPacket,
    step_hsr_stream,
)


def _make_pkt(
    obs_id: int,
    t_obs_us: int,
    state: str = HSR_CLEAR,
    distress: int = 0,
) -> HSRTelemetryPacket:
    """Helper to construct valid HSRTelemetryPacket instances for stream testing."""
    return HSRTelemetryPacket(
        obs_id=obs_id,
        t_obs_us=t_obs_us,
        t_emit_us=t_obs_us + 1_000,
        t_rx_us=t_obs_us + 2_000,
        distress_permille=distress,
        state=state,
        hazard_proximity=False,
        persons_nearby_count=2,
    )


class TestHsrStreamMatrix(unittest.TestCase):
    """Adversarial and boundary scenario matrix for step_hsr_stream()."""

    def test_interleaved_producers_cause_continuous_regression_fail_closed(self) -> None:
        """
        Two independent uncoordinated producers sending alternating sequence counters
        (Producer A: 100, 101...; Producer B: 10, 11...) must cause continuous regressions
        and hold the stream monitor permanently in fail-closed rebase dwell (status None).
        """
        state = HSRStreamState()
        now = 1_000_000

        # Producer A sends obs_id 100
        pA1 = _make_pkt(100, now)
        state, status, _ = step_hsr_stream(state, [pA1], now_us=now)
        self.assertEqual(status, HSR_CLEAR)
        self.assertEqual(state.last_seen_obs_id, 100)

        # Producer B sends obs_id 10 (regression relative to 100)
        now += 32_000
        pB1 = _make_pkt(10, now)
        state, status, _ = step_hsr_stream(state, [pB1], now_us=now)
        self.assertTrue(state.rebase_in_progress)
        self.assertIsNone(status, "Regression must force status to None")
        self.assertEqual(state.rebase_streak, 0)

        # Producer A sends obs_id 101 (regression in terms of counter jump during rebase)
        now += 32_000
        pA2 = _make_pkt(101, now)
        state, status, _ = step_hsr_stream(state, [pA2], now_us=now)
        self.assertTrue(state.rebase_in_progress)
        self.assertEqual(state.rebase_streak, 1)
        self.assertIsNone(status)

        # Producer B sends obs_id 11 (regression relative to 101, resets streak)
        now += 32_000
        pB2 = _make_pkt(11, now)
        state, status, _ = step_hsr_stream(state, [pB2], now_us=now)
        self.assertTrue(state.rebase_in_progress)
        self.assertEqual(state.rebase_streak, 0, "Counter drop back to 11 must wipe rebase streak")
        self.assertIsNone(status)

    def test_backward_timestamp_with_advancing_counter_trips_regression(self) -> None:
        """
        If a producer advances obs_id (10 -> 11) but provides a regressing timestamp
        (t_obs 200ms -> 180ms), it must be classified as a regression and trigger rebase dwell.
        """
        state = HSRStreamState()
        now = 500_000

        p1 = _make_pkt(10, 200_000)
        state, status, stamp = step_hsr_stream(state, [p1], now_us=now)
        self.assertEqual(status, HSR_CLEAR)
        self.assertEqual(stamp, 200_000)

        # Advancing obs_id (11 > 10), but regressing t_obs_us (180_000 < 200_000)
        p2 = _make_pkt(11, 180_000)
        state, status, stamp = step_hsr_stream(state, [p2], now_us=now + 32_000)
        self.assertTrue(state.rebase_in_progress, "Regressing timestamp must trip rebase_in_progress")
        self.assertIsNone(status, "Regressing timestamp must suppress status fail-closed")
        self.assertIsNone(stamp)

    def test_stuttering_producer_triggers_sticky_freeze(self) -> None:
        """
        A stuttering producer that sends (n, n, n+1, n+1) must trip frozen_latched on
        the repeated counter and remain fail-closed.
        """
        state = HSRStreamState()
        now = 100_000

        # Frame 50
        p1 = _make_pkt(50, now)
        state, status, _ = step_hsr_stream(state, [p1], now_us=now)
        self.assertEqual(status, HSR_CLEAR)

        # Repeated Frame 50 (stutter)
        now += 32_000
        p1_stutter = _make_pkt(50, now)
        state, status, _ = step_hsr_stream(state, [p1_stutter], now_us=now)
        self.assertTrue(state.frozen_latched, "Duplicate obs_id must latch sticky freeze")
        self.assertIsNone(status)

        # Advancing Frame 51
        now += 32_000
        p2 = _make_pkt(51, now)
        state, status, _ = step_hsr_stream(state, [p2], now_us=now)
        self.assertTrue(state.frozen_latched, "Single advancing frame cannot clear freeze immediately")
        self.assertEqual(state.rebase_streak, 1)
        self.assertIsNone(status)

        # Repeated Frame 51 (second stutter wipes streak)
        now += 32_000
        p2_stutter = _make_pkt(51, now)
        state, status, _ = step_hsr_stream(state, [p2_stutter], now_us=now)
        self.assertTrue(state.frozen_latched)
        self.assertEqual(state.rebase_streak, 0, "Stutter during recovery must wipe streak")
        self.assertIsNone(status)

    def test_mid_dwell_distress_resets_streak_and_timer(self) -> None:
        """
        During a rebase dwell, any distress packet (MONITOR or CRITICAL) must
        immediately reset rebase_streak to 0 and invalidate rebase_start_t_obs_us.
        """
        # Start directly in rebase with 3 clean ticks accumulated
        state = HSRStreamState(
            last_seen_obs_id=3,
            last_seen_t_obs_us=196_000,
            rebase_in_progress=True,
            rebase_streak=3,
            rebase_start_t_obs_us=100_000,
        )
        now = 228_000

        # Tick 4 delivers advancing frame but with MONITOR severity
        p_distress = _make_pkt(4, now, state=HSR_MONITOR, distress=500)
        state, status, stamp = step_hsr_stream(state, [p_distress], now_us=now)

        self.assertTrue(state.rebase_in_progress)
        self.assertEqual(state.rebase_streak, 0, "Distress during dwell must wipe streak to 0")
        self.assertIsNone(state.rebase_start_t_obs_us, "Distress must reset dwell start timer")
        self.assertIsNone(status)
        self.assertIsNone(stamp)

    def test_intra_batch_regression_fails_closed(self) -> None:
        """
        Within a single batch drain, if an older/regressed datagram appears anywhere
        in arrival sequence, the entire batch must trip rebase and emit None.
        """
        state = HSRStreamState(last_seen_obs_id=10, last_seen_t_obs_us=100_000)
        now = 132_000

        # Batch contains: valid advancing (11), regressed (5), advancing from 5 (6)
        p1 = _make_pkt(11, 130_000)
        p2 = _make_pkt(5, 131_000)
        p3 = _make_pkt(6, 132_000)

        state, status, stamp = step_hsr_stream(state, [p1, p2, p3], now_us=now)
        self.assertTrue(state.rebase_in_progress, "Batch with regression must trip rebase")
        self.assertIsNone(status, "Batch containing regression must emit status None")
        self.assertEqual(state.rebase_streak, 0)
        self.assertEqual(state.last_seen_obs_id, 6)

    def test_timestamp_stagnation_with_advancing_counter(self) -> None:
        """
        Examines current behavior when obs_id advances (10 -> 11) but t_obs_us is
        identical (time stagnation). Confirms it does not trip freeze or regression.
        """
        state = HSRStreamState(last_seen_obs_id=10, last_seen_t_obs_us=200_000)
        now = 202_000

        p = _make_pkt(11, 200_000)  # Identical t_obs_us to previous accepted tick
        state, status, stamp = step_hsr_stream(state, [p], now_us=now)

        self.assertFalse(state.frozen_latched)
        self.assertFalse(state.rebase_in_progress)
        self.assertEqual(status, HSR_CLEAR)
        self.assertEqual(stamp, 200_000)


if __name__ == "__main__":
    unittest.main()
