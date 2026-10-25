# DEMO 9: SCENARIO A EXECUTION EVIDENCE (HEALTHCARE CORRIDOR)

- **Date**: 2026-10-24
- **Branch**: `demo9-hsr-gate-integration`
- **Run ID**: `DEMO9_SCENARIO_A_DISTRESS`
- **World**: `worlds/demo9_hsr_gate.wbt` (Controller: `tiago_supervisory_gate`)
- **Audit File**: `results/DEMO9_SCENARIO_A_DISTRESS/gate_audit.jsonl`
- **Cryptographic Head Seal**: `ca2c52b3125485ab7d8724baa70d289706d419373ddfc456f950651d6b87aba1`

## Invariant Verification Matrix

| # | Invariant | Pre-Registered Specification | Observed Telemetry / Audit Record | Status |
|---|---|---|---|---|
| 1 | **Boot Dwell** | Boot in `TRIPPED`, dwell 1.0s, transition to `AWAITING_RESET`. | `TRIP_PROPOSER_DEAD` at 0.03s, calmed to `AWAITING_RESET` at 1.15s (1.12s dwell). | **PASS** |
| 2 | **Cruise Phase** | Reset accepted, cruise at 2.0 rad/s (~0.196 m/s), corridor > 3.0m. | Reset injected at 1.20s -> `RESET_ACCEPTED` at 1.22s. Cmd 2.00, Meas L=R=2.00 rad/s. Lidar 4716 -> 3816 mm. | **PASS** |
| 3 | **Reflex Trigger** | Injected distress (conf=0.85) at sim t = 4.0s -> HSR `CRITICAL`. | `hsr_status` flipped to `CRITICAL` at 4.000s. | **PASS** |
| 4 | **Reflex Interception** | Gate trips to `TRIP_HSR_CRITICAL` in <= 32ms, motors clamped to 0.0 rad/s. | Tripped on same tick (4.000s, cycle 125). Outputs clamped to L=0.000, R=0.000 rad/s. Lidar 3815 mm (> 346 mm envelope). | **PASS** |
| 5 | **Reset Guard** | Reset refused while hazard active (`RESET_REJECTED_HAZARD`). | Reset requested at 5.02s (cycle 156). Mode held in `TRIPPED`, event `RESET_REJECTED_HAZARD` recorded. | **PASS** |
| 6 | **Audit Replay** | Bit-for-bit replay through pure `step()` with 0 divergences. | `verify_log.py` verified 250/250 cycles through pure core with 0 divergences. | **PASS** |

## Real-Time Performance
- **Control Budget**: 32,000 µs (32 ms)
- **p50 Latency**: 1,266.9 µs
- **p99 Latency**: 2,527.3 µs
- **Max Latency**: 2,633.0 µs (< 8.3% of budget)
