# Demo 8 Evidence: QERRA Supervisory Gate v0.3 (UNRATED, Simulation Only)

Host: Windows 11, Webots R2025a, TIAGo Mobile Base. Non-real-time host.
No safety certification, SIL/PL, ISO 13849 or IEC 61508/62061 compliance is claimed.
All faults are injected via the test harness or process termination.

## 1. Parameters & Reference Points
- Reference Point for all distance figures: **Hokuyo Lidar sensor optical center** (`Hokuyo URG-04LX-UG01(1)`).
- Normal Cruise Speed: $\omega = 2.0\text{ rad/s}$ ($v = 196\text{ mm/s}$).
- Static Standoff Margin: $\text{margin} = 300\text{ mm}$.
- Design Deceleration: $a_{\text{design}} = 500\text{ mm/s}^2$.
- Reaction Time Term: $t_{\text{react}} = 32\text{ ms}$ ($32,000\ \mu\text{s}$).
- Stopping Envelope Formula:
  $$d_{\text{stop}} = \lceil v^2 / (2 a) \rceil + \lceil v \cdot t_{\text{react}} / 10^6 \rceil + \text{margin} = 39 + 7 + 300 = \mathbf{346\text{ mm}}$$

## 2. Complete Scenario Ledger

| ID | Scenario | Expected Outcome | Measured Outcome | Verdict | Run Folder | Anchor (seq / head hash) |
|---|---|---|---|---|---|---|
| A1 | Baseline Obstacle Stop | TRIP_OBSTACLE at envelope | Trip at 58.69s, breach 343 mm, standstill 308 mm (two transient 160 ms proposer stale trips disclosed) | Pass | `results\DEMO8_A1` | 1985 / `2ae25d15...` |
| A2 | Repeat Baseline Stop | Same outcome | Trip at 56.13s, breach 343 mm, standstill 308 mm | Reproduced to the mm in two runs | `results\DEMO8_A2` | 1949 / `5e1923b3...` |
| B | Lidar Freeze during Dwell | TRIP_SENSOR_INVALID | Protocol deviation: wheels already 0 | Archived, replayed bit-for-bit | `results\DEMO8_B` | 685 / `35d12be742fdc1fd4f98957242fe81ad723a68a5545ba68af142efa8501fab84` |
| B2 | Lidar Freeze in RUN | TRIP_SENSOR_INVALID | Fault at 3.0s, trip tick 97 (3.10s), wheels 0 | Pass, replayed bit-for-bit | `results\DEMO8_B2` | 600 / `cb006f5960c31f941df30bc4ebedada147215b47638325ad77ff6c632c9a1495` |
| C | Blind Lidar (all +inf) | TRIP_SENSOR_INVALID | Trip tick 94 (3.01s), wheels 0 | Pass | `results\DEMO8_C` | 446 / `432537d3...` |
| D | Obstacle Outside Corridor ($y = 0.80\text{ m}$) | No trip | Ignored by corridor filter, cruised past for >8s without tripping | Pass | `results\DEMO8_D` | 652 / `d231b875...` |
| D1 | Splice Detection Record | Integrity violation | Line 845 sequence regression caught by cryptographic auditor | Evidence of splice detection | `results\DEMO8_D1` | Line 845 splice finding |
| D1_R2 | Obstacle Inside Corridor ($y = 0.20\text{ m}$) | TRIP_OBSTACLE at envelope | Lidar min 345 mm (envelope 346 mm), wheels 0.0 rad/s, 1349 cycles replayed | Pass, replayed bit-for-bit | `results\DEMO8_D1_R2` | 1348 / `09abf2b28335d4ff2d68282233eac21abc057f9d5193a5d729181dd51cb651f6` |
| E | Proposer Process Crash | TRIP_PROPOSER_STALE | Fault at 3.008s, watchdog fired at 3.136s (age 160 ms), wheels 0 | Pass | `results\DEMO8_E` | 492 / `0cf8fb2e...` |
| F | Injected Reset Recovery | Rejection then acceptance | Early reset rejected at 0.50s, accepted at 1.12s (harness injected) | Pass, replayed bit-for-bit | `results\DEMO8_F` | 351 / `8c2176c2...` |
| F4 | Live Keyboard 'R' Recovery & Exact Stop | RESET_ACCEPTED then TRIP_OBSTACLE | Physical keypress accepted at 5.38s, cruise 54 ticks, exact stop at 346 mm (envelope 346 mm) | Pass, replayed bit-for-bit | `results\DEMO8_F4` | 678 / `95784ba4df7566496c5163cfb63d9cea185c0c5282744e0fd1ef49a7eabeb101` |
| G | NaN Payload Injection | Malformed rejection | MSG_REJECTED_INVALID, cruise continued safely | Pass (NaN only) | `results\DEMO8_G` | 877 / `432f1b56...` |

## 3. Formal Unit Test Suite Verification (106 Tests Passed)
- `test_t09_proposer_restart_new_session_accepted_without_lockout`: Proves gate accepts new proposer monotonic session ID without lockout while latch holds.
- `test_reset_during_hazard_is_rejected`: Proves gate emits `RESET_REJECTED_HAZARD` if reset attempted while obstacle $\le d_{\text{stop}}$.
- `test_over_envelope_proposal_is_clamped_in_run`: Proves 50 rad/s over-speed proposal is strictly clamped to $w_{\max} = 3.0\text{ rad/s}$.
- `test_nan_and_infinity_rejected`: Proves +inf and -inf payloads fail validation.
- `test_oversized_datagram_rejected`: Proves 4096-byte oversized UDP packets are dropped.
- `test_operator_reset_isolated_channel`: Proves forged reset packets sent to proposal port 5005 are ignored.

## 4. STEP 4: B3 Stop-Distance Sweep Specification (Design First)
- **Claim**: Design deceleration ($a_{\text{design}} = 500\text{ mm/s}^2$) vs Webots simulation ground truth for the TIAGo mobile base model.
- **Reference Points**: Distance measured from Hokuyo lidar optical origin; ground truth verified via Supervisor node translation ($X, Y, Z$).
- **Wheel Contact Material**: `default` (verified from Webots official PAL Robotics library).
- **Speed Matrix**:
  - $1.0\text{ rad/s}$ ($98\text{ mm/s}$): $d_{\text{stop}} = 314\text{ mm}$ (braking 10 mm + react 4 mm + margin 300 mm).
  - $2.0\text{ rad/s}$ ($196\text{ mm/s}$): $d_{\text{stop}} = 346\text{ mm}$ (braking 39 mm + react 7 mm + margin 300 mm).
  - $3.0\text{ rad/s}$ ($294\text{ mm/s}$): $d_{\text{stop}} = 397\text{ mm}$ (braking 87 mm + react 10 mm + margin 300 mm).
- **Friction Variations** (via `WorldInfo.contactProperties`):
  - Standard cleanroom: $\mu = 1.0$ (Webots default).
  - Degraded/wet floor: $\mu = 0.5$.
  - High-traction rubber: $\mu = 1.5$.
- **Success Criterion**: $\text{Travel After Trip} \le d_{\text{braking}} + d_{\text{react}}$ so the $300\text{ mm}$ standoff margin is never breached.

## 5. Verified Code Provenance
- `controller`: `ea4fa68928493ca86e922934edb494d3de5a29306373ec703e7e035998262d4a`
- `gate_core`: `421d7fb151cf9d3bdc2b74cb6f105d7bff7de1bcfc0fdda9e7b01bd4f63d2be9`
- `gate_ipc`: `5db54c6979c848de6ca43b814b6435bca081e9016cc122999a832261d518e6f0`
- `gate_lidar`: `078ba1667789972f09d0ed29f7f2fd3e71ea76ec50a9adf9136d8c35b50117f3`
- `gate_log`: `607ddd9c693c5de960e75eec19795f8759ddda294258a41ee03761cff381275c`
- `proposer`: `785252161a49a5eb95411167ef5f7750d77c38de9a5d6b16e8a4002f9c5c196e`
- `verify_log`: `b3905528199595849cbfa7e83044e638516d70565290259d1ff1a86fc15f4245`

## 6. Known Limitations
- Localhost UDP is unauthenticated (untrusted-input handling, not cybersecurity).
- `session_id` is monotonic wall-clock based.
- `raw_valid_points` checks total return count over 240 degrees.
- Single sensor failure requires operator reset.
- Gate has no HSR integration (`hsr_status: None`).
- Physical deployment requires an external safe-torque-off relay.
