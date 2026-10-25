# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""
summarize_run.py - read-only summary of a gate_audit.jsonl.
"""
from __future__ import annotations
import json
import sys

def load(path):
    recs, skipped = [], 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if isinstance(rec, dict) and "seq" in rec and "sim_time_us" in rec and "state" in rec:
                recs.append(rec)
            else:
                skipped += 1
    return recs, skipped

def sig(r):
    inp = r.get("inputs") or {}
    return (
        r.get("state"),
        r.get("reason"),
        tuple(r.get("events") or ()),
        r.get("hsr_status"),
        r.get("cmd_left_urad_s"),
        r.get("cmd_right_urad_s"),
        inp.get("reset_source"),
    )

def secs(r):
    return r["sim_time_us"] / 1_000_000.0

def rad(v):
    return "?" if v is None else f"{v / 1_000_000.0:.3f}"

def main(argv):
    if len(argv) != 2:
        print("Usage: python scripts/summarize_run.py <path_to_gate_audit.jsonl>")
        return 2
    recs, skipped = load(argv[1])
    if not recs:
        print("No control-cycle records found.")
        return 1

    print(f"File            : {argv[1]}")
    print(f"Control records : {len(recs)} (seq {recs[0]['seq']} -> {recs[-1]['seq']}); non-record lines skipped: {skipped}")
    deltas = sorted({recs[i]["sim_time_us"] - recs[i - 1]["sim_time_us"] for i in range(1, len(recs))})
    print(f"Tick deltas (us): {deltas}")
    print(f"Span            : {secs(recs[0]):.3f} s -> {secs(recs[-1]):.3f} s\n")

    runs = []
    for r in recs:
        if runs and runs[-1]["sig"] == sig(r):
            runs[-1]["n"] += 1
            lm = r.get("lidar_min_mm")
            if lm is not None:
                runs[-1]["lmin"] = lm if runs[-1]["lmin"] is None else min(runs[-1]["lmin"], lm)
        else:
            runs.append({"sig": sig(r), "first": r, "n": 1, "lmin": r.get("lidar_min_mm")})

    print("RUNS OF IDENTICAL GATE OUTPUT")
    print(f"{'seq':>4} {'t[s]':>7} {'n':>4}  {'state':<14} {'reason':<22} {'events':<28} {'hsr':<9} {'cmdL':>6} {'cmdR':>6} {'reset':<9} {'lidar_min':>9}")
    for run in runs:
        r = run["first"]
        st, reason, events, hsr, cl, cr, rs = run["sig"]
        ev = ",".join(events) if events else "-"
        lm = "None" if run["lmin"] is None else str(run["lmin"])
        print(f"{r['seq']:>4} {secs(r):>7.3f} {run['n']:>4}  {str(st):<14} {str(reason):<22} {ev:<28} {str(hsr):<9} {rad(cl):>6} {rad(cr):>6} {str(rs or '-'):<9} {lm:>9}")
    print("\nDERIVED FACTS")
    bad = [r for r in recs if r.get("state") != "RUN" and (r.get("cmd_left_urad_s") or 0) != 0 or
           r.get("state") != "RUN" and (r.get("cmd_right_urad_s") or 0) != 0]
    print(f"- Records with non-zero wheel command while state != RUN: {len(bad)}")
    peak = max(max(abs(r.get("cmd_left_urad_s") or 0), abs(r.get("cmd_right_urad_s") or 0)) for r in recs)
    print(f"- Peak |wheel command|: {peak / 1_000_000.0:.3f} rad/s")

    print("- State entries into TRIPPED:")
    prev = None
    for r in recs:
        if r.get("state") == "TRIPPED" and prev != "TRIPPED":
            print(f"    seq {r['seq']:>4}  t={secs(r):7.3f} s  reason={r.get('reason')}")
        prev = r.get("state")

    print("- HSR status changes:")
    prev = None
    first_critical = None
    for r in recs:
        h = r.get("hsr_status")
        if h != prev:
            print(f"    seq {r['seq']:>4}  t={secs(r):7.3f} s  {prev} -> {h}")
            if h == "CRITICAL" and first_critical is None:
                first_critical = r
        prev = h
    if first_critical is not None:
        trip = next((r for r in recs if r.get("reason") == "TRIP_HSR_CRITICAL"), None)
        if trip is not None:
            print(f"    first HSR CRITICAL at seq {first_critical['seq']}; first TRIP_HSR_CRITICAL at seq {trip['seq']} -> latency {trip['seq'] - first_critical['seq']} tick(s)")

    print("- Reset requests (records with reset_source set), grouped by gate answer:")
    groups = {}
    for r in recs:
        src = (r.get("inputs") or {}).get("reset_source")
        if src is None:
            continue
        key = (str(r.get("reason")), ",".join(r.get("events") or ()) or "-", str(src))
        g = groups.setdefault(key, {"n": 0, "first": r, "last": r})
        g["n"] += 1
        g["last"] = r
    for (reason, ev, src), g in groups.items():
        print(f"    {g['n']:>3}x  reason={reason}  events={ev}  source={src}  first seq {g['first']['seq']} t={secs(g['first']):.3f} s, last seq {g['last']['seq']} t={secs(g['last']):.3f} s")
    acc = [r for r in recs if r.get("reason") == "RESET_ACCEPTED"]
    print(f"- RESET_ACCEPTED at: " + (", ".join(f"seq {r['seq']} (t={secs(r):.3f} s)" for r in acc) if acc else "never"))

    run_lidar = [r.get("lidar_min_mm") for r in recs if r.get("state") == "RUN"]
    vals = [v for v in run_lidar if v is not None]
    print(f"- Lidar min while RUN: {min(vals) if vals else 'n/a'} mm minimum over {len(vals)} records with a return; {len(run_lidar) - len(vals)} RUN records with no return (None)")
    print(f"- obstacle_breach true in {sum(1 for r in recs if r.get('obstacle_breach'))} record(s)")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
