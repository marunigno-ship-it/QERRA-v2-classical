# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
Read-only summary of a gate_audit.jsonl: what did the gate actually decide, and when?

It answers three questions that the Webots console does not:
  1. Which (state, reason) pairs occurred, how often, and over which sim-time span?
  2. When did the state change?
  3. Did the robot EVER command a non-zero wheel velocity?

It does NOT verify the hash chain. Use verify_log.py for that.
Standard library only. Usage (from the repository root):
    python scripts/log_reasons.py results/gate_audit.jsonl
"""
import collections
import json
import sys


def main(path: str) -> int:
    rows, bad = [], 0
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                bad += 1
    print(f"file: {path}")
    print(f"lines parsed: {len(rows)}   unparseable lines: {bad}")
    if not rows:
        return 1

    def t(r):
        return r.get("sim_time_us")

    def sec(us):
        return "n/a" if us is None else f"{us / 1e6:7.3f}s"

    runs = sorted({str(r.get("run_id")) for r in rows})
    print(f"run_ids in file: {runs}")
    print(f"sim time span: {sec(t(rows[0]))} .. {sec(t(rows[-1]))}")

    print("\nstate / reason                         count   first       last")
    groups = collections.OrderedDict()
    for r in rows:
        k = (r.get("state"), r.get("reason"))
        g = groups.setdefault(k, [0, t(r), t(r)])
        g[0] += 1
        g[2] = t(r)
    for (state, reason), (n, first, last) in groups.items():
        print(f"{str(state):15} {str(reason):28} {n:6} {sec(first)} {sec(last)}")

    ev = collections.Counter(e for r in rows for e in (r.get("events") or []))
    print("\nevents:", dict(ev) if ev else "none")

    print("\nstate changes (first 20):")
    prev, shown = None, 0
    for r in rows:
        s = r.get("state")
        if s != prev:
            print(f"  {sec(t(r))}  {prev} -> {s}   reason={r.get('reason')}")
            prev, shown = s, shown + 1
            if shown >= 20:
                break

    moving = [r for r in rows if (r.get("cmd_left_urad_s") or 0) != 0 or (r.get("cmd_right_urad_s") or 0) != 0]
    if moving:
        print(f"\nnon-zero wheel command: {len(moving)} ticks, first at {sec(t(moving[0]))}, last at {sec(t(moving[-1]))}")
    else:
        print("\nnon-zero wheel command: NEVER. The robot was commanded to stand still for the whole run.")

    ages = [r["proposal_age_us"] for r in rows if isinstance(r.get("proposal_age_us"), int)]
    mins = [r["lidar_min_mm"] for r in rows if isinstance(r.get("lidar_min_mm"), int)]
    invalid = sum(1 for r in rows if r.get("lidar_valid") is False)
    print(f"proposal age us: min={min(ages) if ages else 'n/a'} max={max(ages) if ages else 'n/a'}")
    print(f"lidar min mm seen: {min(mins) if mins else 'n/a'}   ticks with lidar_valid=false: {invalid}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
