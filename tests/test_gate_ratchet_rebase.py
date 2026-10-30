# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Regression pins for review finding F2: session_id / seq ratchet poisoning.

Before the fix, one accepted datagram carrying an astronomical session_id (or seq) ratcheted
last_session_id / last_seq so far ahead that every legitimate proposal was rejected
(MSG_REJECTED_SEQ) forever. The Gate then sat in TRIP_PROPOSER_STALE and could never reach
AWAITING_RESET, so even an operator reset could not help.

Policy pinned here: the ratchet binds only while a LIVE proposal is held (age < t_watch_us).
When nothing live is held, a FRESH candidate re-bases the ratchet. Replay/regression protection
while a sender is live is unchanged, and re-basing never lifts a latch.

Standard library only; deterministic.
"""
import unittest

from gate.gate_core import (
    Event,
    GateInputs,
    GateParams,
    GateState,
    Mode,
    Proposal,
    Reason,
    RESET_SOURCE_OPERATOR,
    initial_state,
    step,
)

DT = 32_000
N = 5
RANGES = [3.0] * N
POISON_SESSION = 2 ** 62
POISON_SEQ = 2 ** 40


def _params() -> GateParams:
    return GateParams(
        lidar_n_expected=N, dt_us=DT, t_watch_us=150_000, proposer_period_us=33_000,
        lidar_period_us=DT, t_stale_us=96_000, t_dwell_us=1_000_000, max_tick_gap_us=64_000,
        wheel_radius_mm=98, w_min_urad_s=0, w_max_urad_s=3_000_000, a_design_mmps2=500,
        margin_mm=300, min_raw_lidar_returns=5, t_react_us=DT, hsr_required=True,
        t_hsr_stale_us=96_000,
    )


class _Harness:
    def __init__(self):
        self.params = _params()
        self.state = initial_state()
        self.now = 0
        self.seq = 0
        self.last = None

    def tick(self, proposal="auto", reset=None, hsr="CLEAR"):
        self.now += DT
        if proposal == "auto":
            self.seq += 1
            proposal = Proposal(self.seq, self.now, 2_000_000, 2_000_000, 1)
        elif callable(proposal):
            proposal = proposal(self.now)
        inp = GateInputs(
            sim_time_us=self.now, proposal=proposal, ranges_m=RANGES, lidar_stamp_us=self.now,
            reset_source=reset, raw_valid_points=5, hsr_status=hsr, hsr_stamp_us=self.now,
        )
        self.last = step(self.state, self.params, inp)
        self.state = self.last.state
        return self.last

    def to_run(self):
        for _ in range(60):
            self.tick()
            if self.state.mode == Mode.AWAITING_RESET:
                break
        self.tick(reset=RESET_SOURCE_OPERATOR)
        assert self.state.mode == Mode.RUN
        self.tick()
        assert self.last.reason == Reason.PASS
        return self


class TestRatchetPoisoningRecovers(unittest.TestCase):
    def _poison_then_recover(self, make_poison):
        h = _Harness().to_run()
        r = h.tick(proposal=make_poison)
        self.assertNotIn(Event.MSG_REJECTED_SEQ, r.events)  # poison itself is accepted (it is well-formed)
        rejected = 0
        for _ in range(40):  # 1.28 s of otherwise healthy proposals on the original session
            r = h.tick()
            rejected += r.events.count(Event.MSG_REJECTED_SEQ)
        self.assertEqual(h.state.mode, Mode.RUN)
        self.assertEqual(r.reason, Reason.PASS)
        self.assertGreater(r.cmd_left_urad_s, 0)
        self.assertLessEqual(rejected, 5, "lockout must end once the poisoned proposal goes stale")
        self.assertEqual(h.state.last_session_id, 1)  # ratchet re-based onto the live sender

    def test_session_id_poison_recovers(self):
        self._poison_then_recover(lambda now: Proposal(10, now, 2_000_000, 2_000_000, POISON_SESSION))

    def test_seq_poison_recovers(self):
        self._poison_then_recover(lambda now: Proposal(POISON_SEQ, now, 2_000_000, 2_000_000, 1))


class TestRatchetStillProtectsWhileLive(unittest.TestCase):
    def test_replay_and_older_session_rejected_while_proposal_is_live(self):
        h = _Harness().to_run()
        live_seq = h.seq
        r = h.tick(proposal=lambda now: Proposal(live_seq, now, 2_000_000, 2_000_000, 1))  # duplicate seq
        self.assertIn(Event.MSG_REJECTED_SEQ, r.events)
        r = h.tick(proposal=lambda now: Proposal(live_seq + 50, now, 2_000_000, 2_000_000, 0))  # older session
        self.assertIn(Event.MSG_REJECTED_SEQ, r.events)

    def test_higher_session_restart_still_accepted_while_live(self):
        h = _Harness().to_run()
        r = h.tick(proposal=lambda now: Proposal(0, now, 2_000_000, 2_000_000, 2))
        self.assertNotIn(Event.MSG_REJECTED_SEQ, r.events)
        self.assertEqual(h.state.last_session_id, 2)


class TestRebaseGuards(unittest.TestCase):
    def _stale_poisoned_state(self):
        old = Proposal(POISON_SEQ, 0, 2_000_000, 2_000_000, POISON_SESSION)
        return GateState(
            mode=Mode.TRIPPED, last_tick_us=968_000, clear_since_us=None, held=old,
            last_seq=POISON_SEQ, last_cmd=(0, 0), last_session_id=POISON_SESSION,
        )

    def _inp(self, now, proposal):
        return GateInputs(
            sim_time_us=now, proposal=proposal, ranges_m=RANGES, lidar_stamp_us=now,
            raw_valid_points=5, hsr_status="CLEAR", hsr_stamp_us=now,
        )

    def test_stale_candidate_does_not_rebase(self):
        """A replayed/old datagram (stamp older than t_watch) must not take over a stale ratchet."""
        now = 1_000_000
        stale_cand = Proposal(5, now - 400_000, 2_000_000, 2_000_000, 1)
        r = step(self._stale_poisoned_state(), _params(), self._inp(now, stale_cand))
        self.assertIn(Event.MSG_REJECTED_SEQ, r.events)
        self.assertEqual(r.state.last_session_id, POISON_SESSION)

    def test_future_or_invalid_candidate_does_not_rebase(self):
        now = 1_000_000
        future = Proposal(5, now + DT, 2_000_000, 2_000_000, 1)
        r = step(self._stale_poisoned_state(), _params(), self._inp(now, future))
        self.assertIn(Event.MSG_REJECTED_FUTURE, r.events)
        invalid = Proposal(-1, now, 2_000_000, 2_000_000, 1)
        r = step(self._stale_poisoned_state(), _params(), self._inp(now, invalid))
        self.assertIn(Event.MSG_REJECTED_INVALID, r.events)
        self.assertEqual(r.state.last_session_id, POISON_SESSION)

    def test_rebase_does_not_lift_the_latch(self):
        """Re-basing restores proposer liveness only. Mode stays TRIPPED, wheels stay at zero."""
        now = 1_000_000
        fresh = Proposal(5, now, 2_000_000, 2_000_000, 1)
        r = step(self._stale_poisoned_state(), _params(), self._inp(now, fresh))
        self.assertEqual(r.state.last_session_id, 1)
        self.assertEqual(r.state.mode, Mode.TRIPPED)
        self.assertEqual((r.cmd_left_urad_s, r.cmd_right_urad_s), (0, 0))
        self.assertEqual(r.reason, Reason.LATCHED_DWELL)


if __name__ == "__main__":
    unittest.main()
