# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Regression pins for Safety Concept Claim C-7 (stacked dwell), enforced inside the Gate core.

Review finding F1: the Gate's own dwell used to count HSR "MONITOR" as calm, and reset needed
only a "CLEAR" status on the reset tick. With a raw (unstabilised) status stream, reset could be
accepted ~1.1 s after the last CRITICAL on a single CLEAR reading. These tests pin the fix:
the Gate itself must observe a continuous, fresh HSR "CLEAR" run of >= t_dwell_us before it
enters AWAITING_RESET, and before it accepts a reset.

Scope: enforced only when GateParams.hsr_required is True. Legacy mode (False) is unchanged.
Standard library only; deterministic; no sockets, files or clocks.
"""
import unittest

from gate.gate_core import (
    Event,
    GateInputs,
    GateParams,
    Mode,
    Proposal,
    Reason,
    RESET_SOURCE_OPERATOR,
    initial_state,
    step,
)

DT = 32_000
N = 5
CLEAN_RANGES = [3.0] * N


def _params(*, hsr_required: bool) -> GateParams:
    return GateParams(
        lidar_n_expected=N,
        dt_us=DT,
        t_watch_us=150_000,
        proposer_period_us=33_000,
        lidar_period_us=DT,
        t_stale_us=96_000,
        t_dwell_us=1_000_000,
        max_tick_gap_us=64_000,
        wheel_radius_mm=98,
        w_min_urad_s=0,
        w_max_urad_s=3_000_000,
        a_design_mmps2=500,
        margin_mm=300,
        min_raw_lidar_returns=5,
        t_react_us=DT,
        hsr_required=hsr_required,
        t_hsr_stale_us=96_000,
    )


class _Harness:
    """Drives step() one 32 ms tick at a time with a healthy lidar and proposer."""

    def __init__(self, params: GateParams):
        self.params = params
        self.state = initial_state()
        self.now = 0
        self.seq = 0
        self.last = None

    def tick(self, hsr="CLEAR", hsr_stamp="now", reset=None, proposal="auto", advance=DT):
        self.now += advance
        if proposal == "auto":
            self.seq += 1
            proposal = Proposal(self.seq, self.now, 2_000_000, 2_000_000, 1)
        stamp = self.now if hsr_stamp == "now" else hsr_stamp
        inp = GateInputs(
            sim_time_us=self.now,
            proposal=proposal,
            ranges_m=CLEAN_RANGES,
            lidar_stamp_us=self.now,
            reset_source=reset,
            raw_valid_points=5,
            hsr_status=hsr,
            hsr_stamp_us=stamp,
        )
        self.last = step(self.state, self.params, inp)
        self.state = self.last.state
        return self.last

    def run(self, n, **kw):
        for _ in range(n):
            self.tick(**kw)
        return self.last

    def to_run(self):
        """Boot (TRIPPED) -> dwell -> AWAITING_RESET -> operator reset -> RUN."""
        for _ in range(60):
            self.tick()
            if self.state.mode == Mode.AWAITING_RESET:
                break
        assert self.state.mode == Mode.AWAITING_RESET
        self.tick(reset=RESET_SOURCE_OPERATOR)
        assert self.state.mode == Mode.RUN
        self.tick()
        assert self.last.reason == Reason.PASS
        return self


class TestC7HsrClearDwellInGate(unittest.TestCase):
    def setUp(self):
        self.p = _params(hsr_required=True)

    def test_monitor_does_not_count_as_clear_dwell(self):
        """F1: ~1.1 s of MONITOR after CRITICAL must NOT reach AWAITING_RESET."""
        h = _Harness(self.p).to_run()
        h.run(5, hsr="CRITICAL")
        r = h.run(34, hsr="MONITOR")  # 34 ticks = 1.088 s > t_dwell
        self.assertEqual(h.state.mode, Mode.TRIPPED)
        self.assertEqual(r.reason, Reason.LATCHED_DWELL)
        self.assertEqual((r.cmd_left_urad_s, r.cmd_right_urad_s), (0, 0))

    def test_single_clear_tick_after_monitor_cannot_reset(self):
        """F1 exploit path: CRITICAL -> MONITOR (1.1 s) -> one CLEAR tick + reset => must be refused."""
        h = _Harness(self.p).to_run()
        h.run(5, hsr="CRITICAL")
        h.run(34, hsr="MONITOR")
        r = h.tick(hsr="CLEAR", reset=RESET_SOURCE_OPERATOR)
        self.assertNotEqual(h.state.mode, Mode.RUN)
        self.assertNotEqual(r.reason, Reason.RESET_ACCEPTED)
        self.assertEqual((r.cmd_left_urad_s, r.cmd_right_urad_s), (0, 0))

    def test_full_clear_dwell_then_reset_is_accepted_with_standstill(self):
        """After a continuous CLEAR run >= t_dwell the Gate arms; reset works; reset tick commands (0,0)."""
        h = _Harness(self.p).to_run()
        h.run(5, hsr="CRITICAL")
        h.run(34, hsr="MONITOR")
        armed_at = None
        for _ in range(60):
            h.tick(hsr="CLEAR")
            if h.state.mode == Mode.AWAITING_RESET:
                armed_at = h.now
                break
        self.assertIsNotNone(armed_at, "Gate never armed after a continuous CLEAR run")
        r = h.tick(hsr="CLEAR", reset=RESET_SOURCE_OPERATOR)
        self.assertEqual(h.state.mode, Mode.RUN)
        self.assertEqual(r.reason, Reason.RESET_ACCEPTED)
        self.assertEqual((r.cmd_left_urad_s, r.cmd_right_urad_s), (0, 0))  # reset-tick standstill invariant
        r2 = h.tick(hsr="CLEAR")
        self.assertEqual(r2.reason, Reason.PASS)
        self.assertGreater(r2.cmd_left_urad_s, 0)

    def test_direct_critical_to_clear_timing_is_unchanged(self):
        """Demo 9 path (no MONITOR stage): arms 32 ticks (1.024 s) after the first CLEAR tick."""
        h = _Harness(self.p).to_run()
        h.run(5, hsr="CRITICAL")
        first_clear = h.now + DT
        armed_at = None
        for _ in range(60):
            h.tick(hsr="CLEAR")
            if h.state.mode == Mode.AWAITING_RESET:
                armed_at = h.now
                break
        self.assertIsNotNone(armed_at)
        self.assertEqual(armed_at - first_clear, 1_024_000)

    def test_monitor_blip_after_arming_restarts_the_clear_dwell(self):
        """Armed (AWAITING_RESET) -> one MONITOR tick -> immediate CLEAR + reset must be refused."""
        h = _Harness(self.p).to_run()
        h.run(5, hsr="CRITICAL")
        for _ in range(60):
            h.tick(hsr="CLEAR")
            if h.state.mode == Mode.AWAITING_RESET:
                break
        self.assertEqual(h.state.mode, Mode.AWAITING_RESET)
        h.tick(hsr="MONITOR")
        r = h.tick(hsr="CLEAR", reset=RESET_SOURCE_OPERATOR)
        self.assertNotEqual(r.reason, Reason.RESET_ACCEPTED)
        self.assertIn(Event.RESET_REJECTED_NOT_READY, r.events)
        self.assertEqual((r.cmd_left_urad_s, r.cmd_right_urad_s), (0, 0))
        # ...and recovers only after a full fresh CLEAR run.
        for _ in range(40):
            r = h.tick(hsr="CLEAR", reset=RESET_SOURCE_OPERATOR)
            if r.reason == Reason.RESET_ACCEPTED:
                break
        self.assertEqual(h.state.mode, Mode.RUN)

    def test_stale_or_invalid_hsr_breaks_the_clear_run(self):
        """A stale stamp mid-dwell must clear hsr_clear_since_us, not just pause it."""
        h = _Harness(self.p).to_run()
        h.run(5, hsr="CRITICAL")
        h.run(20, hsr="CLEAR")
        self.assertIsNotNone(h.state.hsr_clear_since_us)
        h.tick(hsr="CLEAR", hsr_stamp=h.now - 200_000)  # older than t_hsr_stale_us
        self.assertIsNone(h.state.hsr_clear_since_us)
        h.tick(hsr="garbage")
        self.assertIsNone(h.state.hsr_clear_since_us)

    def test_tick_gap_restarts_the_clear_run(self):
        """A gap larger than max_tick_gap_us is not 'continuous'."""
        h = _Harness(self.p).to_run()
        h.run(5, hsr="CRITICAL")
        h.run(20, hsr="CLEAR")
        before = h.state.hsr_clear_since_us
        h.tick(hsr="CLEAR", advance=DT * 3)  # 96 ms gap > 64 ms
        self.assertGreater(h.state.hsr_clear_since_us, before)
        self.assertEqual(h.state.hsr_clear_since_us, h.now)

    def test_legacy_mode_is_unchanged(self):
        """hsr_required=False with no HSR stream still arms after t_dwell (Demo 8 behaviour)."""
        h = _Harness(_params(hsr_required=False))
        armed = False
        for _ in range(60):
            h.tick(hsr=None, hsr_stamp=None)
            if h.state.mode == Mode.AWAITING_RESET:
                armed = True
                break
        self.assertTrue(armed)


if __name__ == "__main__":
    unittest.main()
