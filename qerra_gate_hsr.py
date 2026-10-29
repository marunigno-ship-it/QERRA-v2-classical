"""Repro harness against the real gate_core / StabilizedHSR.
Reads the repo, does not modify it.
Usage (from the repo root, e.g. in the PyCharm terminal):
    python qerra_gate_hsr.py            # uses the current directory as repo root
    python qerra_gate_hsr.py <repo_root>
Run against your local branch to compare with what origin/main (b473277) shows.
"""
import logging
import os
import socket
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
sys.path.insert(0, REPO)
logging.disable(logging.CRITICAL)

from gate.gate_core import (GateInputs, Proposal, Mode, initial_state, step)  # noqa: E402
from gate.gate_config import get_live_gate_params  # noqa: E402
from gate.gate_ipc import (create_udp_receiver, drain_hsr_telemetry, poll_operator_reset)  # noqa: E402
from gate.hsr_telemetry import is_perception_frozen  # noqa: E402
from hsr.hysteresis_wrapper import StabilizedHSR  # noqa: E402
from hsr.qerra_hsr import HSRInput  # noqa: E402
from scripts.synthetic_hsr_producer import build_payload  # noqa: E402

N = 20
DT = 32_000
P = get_live_gate_params(N, hsr_required=True)


class Sim:
    def __init__(self, session=1000):
        self.st = initial_state()
        self.now = 0
        self.seq = 0
        self.session = session
        self.last = None

    def tick(self, hsr="CLEAR", hsr_stamp="now", proposal="auto", reset=None):
        self.now += DT
        if proposal == "auto":
            proposal = Proposal(self.seq, self.now, 2_000_000, 2_000_000, self.session)
            self.seq += 1
        stamp = self.now if hsr_stamp == "now" else hsr_stamp
        inp = GateInputs(
            sim_time_us=self.now, proposal=proposal, ranges_m=[3.0] * N,
            lidar_stamp_us=self.now, reset_source=reset, raw_valid_points=100,
            hsr_status=hsr, hsr_stamp_us=stamp,
        )
        r = step(self.st, P, inp)
        self.st = r.state
        self.last = r
        return r

    def t(self):
        return self.now / 1e6


def bring_up(sim):
    """TRIPPED start -> AWAITING_RESET -> operator reset -> RUN."""
    for _ in range(80):
        sim.tick()
        if sim.st.mode == Mode.AWAITING_RESET:
            break
    r = sim.tick(reset="operator")
    assert sim.st.mode == Mode.RUN, (sim.st.mode, r.reason, r.events)
    r = sim.tick()
    assert r.reason == "PASS" and r.cmd_left_urad_s > 0, r.reason
    return sim


print("=" * 70)
print("A. Session / seq ratchet poisoning (one datagram on UDP 5005)")
sim = bring_up(Sim(session=1000))
sim.tick(proposal=Proposal(10_000_000, sim.now + DT, 2_000_000, 2_000_000, session_id=2 ** 62))
seen = {}
for _ in range(200):  # ~6.4 s of otherwise healthy proposer traffic (session 1000)
    r = sim.tick()
    for e in r.events:
        seen[e] = seen.get(e, 0) + 1
print(f"  after poison + 6.4 s of healthy proposals: mode={sim.st.mode.value} reason={sim.last.reason} events={seen}")
a1_ok = sim.st.mode == Mode.RUN and seen.get("MSG_REJECTED_SEQ", 0) <= 5
sim = bring_up(Sim(session=1000))
sim.tick(proposal=Proposal(2 ** 40, sim.now + DT, 2_000_000, 2_000_000, session_id=1000))
seen = {}
for _ in range(200):
    r = sim.tick()
    for e in r.events:
        seen[e] = seen.get(e, 0) + 1
print(f"  seq-only poison (same session):        mode={sim.st.mode.value} reason={sim.last.reason} events={seen}")
a2_ok = sim.st.mode == Mode.RUN and seen.get("MSG_REJECTED_SEQ", 0) <= 5
print(f"  EXPECT (F2: lockout ends once the poisoned proposal goes stale; <=5 rejections, mode RUN)  ->  "
      f"{'PASS' if (a1_ok and a2_ok) else 'FAIL  (proposer locked out by one poisoned datagram)'}")

print("=" * 70)
print("B. HSR stale boundary (stamp frozen at T, everything else healthy)")
sim = bring_up(Sim())
T = sim.now
for k in range(1, 6):
    r = sim.tick(hsr="CLEAR", hsr_stamp=T)
    print(f"  tick +{k * 32:3d} ms: hsr_age={r.record['hsr_age_us']:>7} us -> mode={sim.st.mode.value:<8} reason={r.reason}")

print("=" * 70)
print("C. 'Dual dwell' with RAW (unstabilised) status stream: CRITICAL -> MONITOR 1.1 s -> 1 tick CLEAR + reset")
sim = bring_up(Sim())
sim.tick(hsr="CRITICAL")
for _ in range(10):
    sim.tick(hsr="CRITICAL")
t_crit_end = sim.t()
accepted_at = None
for _ in range(34):  # 34 ticks = 1.09 s of MONITOR
    sim.tick(hsr="MONITOR")
print(f"  after ~1.1 s of MONITOR: mode={sim.st.mode.value} reason={sim.last.reason}")
mode_after_monitor = sim.st.mode
r = sim.tick(hsr="CLEAR", reset="operator")
print(f"  single CLEAR tick + reset at t={sim.t():.3f}s (last CRITICAL t={t_crit_end:.3f}s): "
      f"mode={sim.st.mode.value} reason={r.reason} events={r.events}")
c_ok = (mode_after_monitor != Mode.AWAITING_RESET) and (r.reason != "RESET_ACCEPTED")
print(f"  EXPECT (C-7 enforced by the Gate): not armed by MONITOR, reset refused  ->  "
      f"{'PASS' if c_ok else 'FAIL  (Gate accepted reset on 1 CLEAR tick after MONITOR)'}")

print("=" * 70)
print("D. Same through StabilizedHSR (as the live controller does): when does reset get accepted?")
sim_clock = [0.0]
wrap = StabilizedHSR(clock=lambda: sim_clock[0])
sim = Sim()


def drive(conf, persons, reset=None):
    sim_clock[0] = (sim.now + DT) / 1e6
    res = wrap.evaluate(HSRInput(conf, persons, False, True))
    return sim.tick(hsr=res.status.value, reset=reset), res.status.value


# bring-up with wrapper
for _ in range(80):
    r, s = drive(0.0, 0)
    if sim.st.mode == Mode.AWAITING_RESET:
        break
r, s = drive(0.0, 0, reset="operator")
assert sim.st.mode == Mode.RUN
prev = None
log = []
accepted = None
t_distress_end = None
while sim.t() < 14.0:
    t = sim.now / 1e6 + DT / 1e6
    if t < 4.0:
        conf, persons = 0.0, 0
    elif t < 7.0:
        conf, persons = 0.85, 0
    elif t < 9.6:
        conf, persons = 0.50, 2      # raw MONITOR (mild distress, others nearby)
        t_distress_end = t_distress_end or t
    else:
        conf, persons = 0.0, 0
    r, s = drive(conf, persons, reset="operator" if t >= 7.0 and accepted is None else None)
    key = (s, sim.st.mode.value, r.reason)
    if key != prev:
        log.append((round(sim.t(), 3), s, sim.st.mode.value, r.reason, r.events))
        prev = key
    if r.reason == "RESET_ACCEPTED" and accepted is None:
        accepted = sim.t()
for row in log:
    print("  t=%6.3f hsr=%-8s mode=%-14s reason=%-22s events=%s" % row)
print(f"  reset accepted at t={accepted}")
first_clear = next((row[0] for row in log if row[1] == "CLEAR" and row[0] > 4.0), None)
if accepted is None or first_clear is None:
    d_ok = False
else:
    d_ok = (accepted - first_clear) >= 1.0 - 1e-9
print(f"  first CLEAR tick t={first_clear}; reset accepted {None if accepted is None else round(accepted - first_clear, 3)} s later")
print(f"  EXPECT (Gate observes >= 1.0 s of CLEAR before accepting reset)  ->  "
      f"{'PASS' if d_ok else 'FAIL  (reset accepted on the first CLEAR tick)'}")

print("=" * 70)
print("E. StabilizedHSR dwell is wall-span, not continuous observation")
c = [0.0]
w = StabilizedHSR(clock=lambda: c[0])
for t, conf in [(0.0, 0.85), (0.1, 0.0), (1.2, 0.0)]:
    c[0] = t
    res = w.evaluate(HSRInput(conf, 0, False, True))
    print(f"  t={t:4.1f}s conf={conf} -> wrapper status {res.status.value}  (only 2 calm samples, 1.1 s apart)")

print("=" * 70)
print("F. Recovery needs a live proposer: dead proposer after HSR clears")
sim = bring_up(Sim())
for _ in range(5):
    sim.tick(hsr="CRITICAL")
for _ in range(250):  # 8 s, HSR CLEAR, proposer silent
    sim.tick(hsr="CLEAR", proposal=None)
print(f"  8 s after HSR clear, proposer silent: mode={sim.st.mode.value} reason={sim.last.reason}")
sim = bring_up(Sim())
for _ in range(5):
    sim.tick(hsr="CRITICAL")
n = 0
progress = []
for i in range(300):
    gap = (i % 28 >= 5 and i % 28 < 10)  # a 160 ms proposer hiccup every ~0.9 s
    sim.tick(hsr="CLEAR", proposal=None if gap else "auto")
    progress.append(sim.st.mode.value)
print(f"  proposer hiccup (160 ms) every 0.9 s for 9.6 s: reaches AWAITING_RESET = {'AWAITING_RESET' in progress}")

print("=" * 70)
print("G. Operator-reset channel authenticity (UDP 5006 semantics)")
rx = create_udp_receiver(15006)
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    tx.sendto(b"operator", ("127.0.0.1", 15006))
    import time
    time.sleep(0.05)
    print(f"  datagram 'operator' from an arbitrary local socket -> poll_operator_reset() = {poll_operator_reset(rx)!r}")
finally:
    rx.close()
    tx.close()

print("=" * 70)
print("H. Asynchronous HSR Telemetry & Worst-Severity-Wins UDP Drain (Phase 2)")
# Bring up Gate into live RUN mode first so simulation time is established
sim = bring_up(Sim())
t_sim = sim.now + DT

rx_hsr = create_udp_receiver(15008)
tx_hsr = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
hsr_addr = ("127.0.0.1", 15008)
try:
    # Burst 3 fresh packets in one tick: CLEAR -> CRITICAL (distress 850) -> CLEAR
    p1 = build_payload(obs_id=1, sim_time_us=t_sim, distress_permille=0)
    p2 = build_payload(obs_id=2, sim_time_us=t_sim, distress_permille=850)
    p3 = build_payload(obs_id=3, sim_time_us=t_sim, distress_permille=0)
    for p in (p1, p2, p3):
        tx_hsr.sendto(p, hsr_addr)
    import time
    time.sleep(0.02)

    pkt, drained_count = drain_hsr_telemetry(rx_hsr, t_rx_us=t_sim + 1000)
    print(f"  drained {drained_count} datagrams from UDP 15008: winning state={getattr(pkt, 'state', None)} "
          f"obs_id={getattr(pkt, 'obs_id', None)} distress={getattr(pkt, 'distress_permille', None)}")

    r = sim.tick(hsr=pkt.state, hsr_stamp=pkt.t_obs_us)
    print(f"  Gate step evaluation with drained packet: mode={sim.st.mode.value} reason={r.reason} "
          f"cmd=({r.cmd_left_urad_s}, {r.cmd_right_urad_s}) urad/s")

    frozen_detected = is_perception_frozen(current_obs_id=2, last_seen_obs_id=2)

    h_ok = (
        drained_count == 3
        and pkt is not None
        and pkt.state == "CRITICAL"
        and pkt.obs_id == 2
        and sim.st.mode == Mode.TRIPPED
        and r.reason == "TRIP_HSR_CRITICAL"
        and r.cmd_left_urad_s == 0
        and r.cmd_right_urad_s == 0
        and frozen_detected
    )
    print(f"  EXPECT (Worst-severity wins over UDP batch & immediate CRITICAL trip)  ->  "
      f"{'PASS' if h_ok else 'FAIL'}")
finally:
    rx_hsr.close()
    tx_hsr.close()
