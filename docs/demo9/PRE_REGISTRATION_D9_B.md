# Demo 9 - Scenario B Evidence Record

Scenario: acute distress reflex, hysteresis recovery, mission resumption (14 s, closed loop).
Run ID: `DEMO9_SCENARIO_B_FINAL`
Recorded: 24 Oct 2026, Webots R2025a, launched from the Webots window (standalone mode).

## 1. Artifacts

| Item | Value |
|---|---|
| World | `worlds/demo9_hsr_gate.wbt`, SHA-256 `F529C926E89DAE7591C9FB7A46A432DBEDA41B54351970DF9AF6137E50DA6A41` |
| Controller | `controllers/tiago_supervisory_gate/tiago_supervisory_gate.py` |
| Controller SHA-256 | `e1e6f63ceb2b681b0f36151b70adfdc6192d5960e98154dc3e5e3d096c71b0d7` (equals `manifest.json` `code_hashes.controller`) |
| Gate version | 0.3 |
| Audit log | `results/DEMO9_SCENARIO_B_FINAL/gate_audit.jsonl` |
| Records | 438 (sequence 0 to 437), dt = 32 ms |
| Head hash (seal) | `eccb0d85416cf4a651205f34f3cc0d9275bff6e2b3baa512e4b23dbef0c2714a` |
| Replay | `verify_log.py ... --replay`: all 438 control cycles reproduced bit-for-bit through pure `step()` |
| Replay notice | `hsr_required: run=True vs default=False` (enforced as trip condition) |
| Attempts | 2 recorded runs, 1 clean. `DEMO9_SCENARIO_B_TAKE1`: executed cruise, distress trip, reset refusal, recovery reset (9.98s); tripped at 10.27s on host scheduling jitter (`TRIP_PROPOSER_STALE`). `DEMO9_SCENARIO_B_FINAL`: executed cleanly start to finish. |

## 2. Observed Timeline (Simulation Time)

Tick = sim time / 0.032 s. Audit-log `seq` = tick - 1.

| Event | Tick | Sim time | Log / Console Evidence |
|---|---|---|---|
| Boot trip | 1 | 0.03 s | `START -> TRIPPED`, `TRIP_PROPOSER_DEAD` |
| Reset 1, first request refused | 38 | 1.216 s | `LATCHED_DWELL`, `RESET_REJECTED_NOT_READY` |
| Reset 1 accepted, cruise starts | 41 | 1.312 s | `RESET_ACCEPTED`, mode `RUN`, cmd 2.00 rad/s |
| Distress injected, HSR `CRITICAL`, gate trips | 125 | 4.000 s | `TRIP_HSR_CRITICAL`, L=R=0.000 rad/s (Cycle 125, 0 latency) |
| Reset 2 refused | 157 | 5.024 s | reason `TRIP_HSR_CRITICAL`, event `RESET_REJECTED_HAZARD` |
| Distress input returns to 0 | 219 | 7.008 s | event active while t < 7.0 s |
| HSR `CRITICAL` to `CLEAR` | 251 | 8.032 s | `[HSR] status CRITICAL -> CLEAR` (1.024 s hysteresis dwell) |
| Reset 3 first request refused | 257 | 8.224 s | `LATCHED_DWELL`, `RESET_REJECTED_NOT_READY` |
| Reset 3 accepted, cruise resumes | 283 | 9.056 s | `RESET_ACCEPTED`, mode `RUN` (1.024 s gate dwell completed) |
| End of run | 438 | 14.016 s | `QERRA_END_AT_S reached`, log cleanly closed |

## 3. Invariants Verification

| ID | Invariant | Result | Evidence |
|---|---|---|---|
| B1 | Boot hold at 0.000 rad/s until dwell completes | Pass | Actuators 0.0 rad/s through 1.312 s |
| B2 | Cruise at 2.000 rad/s from reset to 4.000 s | Pass | Cmd 2.00, Meas 2.00 rad/s |
| B3 | Reflex emergency stop on injection tick (<= 32 ms) | Pass | Cycle 125 (0 ticks added latency) |
| B4 | Reset during active distress refused (`RESET_REJECTED_HAZARD`) | Pass | Event recorded at 5.024 s |
| B5 | Dual dwell stacking enforced (HSR dwell + Gate dwell) | Pass | Accepted at 9.056 s; earlier requests refused |
| B6 | Post-recovery reset restores velocity to 2.000 rad/s | Pass | Resumed at 9.056 s through 14.016 s |
| B7 | No obstacle collision (corridor clear) | Pass | Lidar min > 3.8 m throughout |
| B8 | Deterministic Replay | Pass | 438/438 cycles bit-for-bit, 0 divergences |

## 4. Control for Causality
`DEMO9_SCENARIO_A_CONTROL` (same world, distress disabled) cruised through t = 4.0 s without tripping, proving distress injection is the sole causal trigger.

## 5. Limitations and Non-Claims
1. **Injected Distress Signal**: Distress is an injected confidence (0.85), not a live CV model.
2. **Automated Resets**: Resets were injected by the harness.
3. **Software Safety Function**: Tested in simulation, not full hardware certification.
4. **Replay-verified Live Mode**: Replay is 100% deterministic; live UDP mode subject to host scheduling.
5. **Standalone Controller Defaults**: Compiled-in defaults allow clean standalone Webots execution.
