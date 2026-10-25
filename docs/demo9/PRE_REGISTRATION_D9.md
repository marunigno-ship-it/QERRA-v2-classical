<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Marussa Metocharaki -->

# Demo 9 Pre-Registration: Supervisory Gate + HSR Reflex Integration

* **Author:** Marussa Metocharaki
* **Date:** 23 October 2026
* **Branch:** `demo9-hsr-gate-integration`
* **Target System:** QERRA Supervisory Gate v0.3 + QERRA-HSR v0.1
* **Platform:** PAL Robotics TIAGo mobile base in Webots R2025a
* **Status:** Pre-registered baseline (frozen prior to recording)

---

## 1. What Demo 9 Tests

Demo 7 proved that the Supervisory Gate stops for physical obstacles seen by the lidar.  
Demo 8 proved that the Gate trips fail-closed when the lidar freezes or the planner process stalls.

**Demo 9 tests one specific question:**
> When the corridor ahead is completely empty and all sensors are healthy, can the QERRA-HSR reflex layer independently command the Supervisory Gate to cut wheel velocities to zero, latch the stop, and refuse reset while the distress condition persists?

The goal is to prove **one authoritative command path**: HSR does not touch the motors; it evaluates human distress and reports its status to the Gate, which enforces the stop.

---

## 2. Experimental Setup (Scenario A)

* **Environment:** The transport corridor from Demo 7/8 ($0.64\text{ m}$ lane width).
* **Corridor Path:** Completely clear ($> 3.0\text{ m}$ ahead). No obstacle carts in the lane.
* **Cruise Speed:** Commanded at $2.0\text{ rad/s}$ forward rotation ($\approx 0.196\text{ m/s}$ on $98\text{ mm}$ wheels).
* **The Injected Event:** At $t = 4.0\text{ s}$ of simulation time, the test harness injects an acute human distress event (`QERRA_HSR_EVENT=distress`).
* **HSR Evaluation:** 
  * `distress_confidence = 0.85` (exceeds the 0.75 critical threshold).
  * `persons_nearby_count = 0` (person is alone).
  * Vectors activated: `immediate_physical_distress` + `human_isolation`.
  * HSR status evaluates to `CRITICAL`.

---

## 3. Stopping Envelope Math (Frozen Baseline)

The stopping envelope parameters match the hardened Demo 8 baseline:

$$d_{\text{stop}} = \left\lceil \frac{v_{\text{ref}}^2}{2 \cdot a_{\text{design}}} \right\rceil + \left\lceil \frac{v_{\text{ref}} \cdot t_{\text{react}}}{10^6} \right\rceil + d_{\text{margin}}$$

* $v_{\text{ref}} = 196\text{ mm/s}$
* $a_{\text{design}} = 500\text{ mm/s}^2$ ($0.5\text{ m/s}^2$)
* $t_{\text{react}} = 32\,000\ \mu\text{s}$ ($32\text{ ms}$ reaction allowance)
* $d_{\text{margin}} = 300\text{ mm}$
* **Calculated stopping envelope:** $39 + 7 + 300 = \mathbf{346\text{ mm}}$.

---

## 4. Pre-Registered Pass/Fail Criteria

Before recording the run, I freeze the following 6 acceptance checks:

1. **Independent Trip:** At $t = 4.0\text{ s}$, when HSR reports `CRITICAL`, the Gate must transition to `TRIPPED` with reason `TRIP_HSR_CRITICAL`. The obstacle breach flag must remain `False`.
2. **Software Command Latency:** The Gate must command `0.0 rad/s` to both wheels within one simulation tick ($32\text{ ms}$) of receiving `CRITICAL`.
3. **Latched Stop:** The robot must stay stationary. No forward command may be issued while HSR remains `CRITICAL`.
4. **Reset Refusal:** If an operator reset (Key 'R') is attempted while distress is still active, the Gate must reject it (`RESET_REJECTED_HAZARD`) and hold the wheels at zero.
5. **Fail-Closed on Missing HSR:** If `hsr_required = True` and HSR data is missing (`None`) or corrupted, the Gate must trip immediately with `TRIP_HSR_INVALID`. Silence is not treated as safe.
6. **Bit-for-Bit Replay:** The resulting `gate_audit.jsonl` log must verify cleanly with `verify_log.py --replay`, reproducing every control decision through the pure `step()` core with zero discrepancies.

---

## 5. What This Run Does and Does Not Claim

* **Not an autonomous computer vision claim:** Demo 9 evaluates the execution guard under an injected telemetry signal (`QERRA_HSR_EVENT=distress`). It does not evaluate a real camera neural network detecting a human fall.
* **Commanded stop vs. physical standstill:** Issuing `0.0 rad/s` in $32\text{ ms}$ is a software command. Physical stopping distance depends on simulated tire traction and robot momentum.
* **Simulation boundary:** This experiment runs in Webots R2025a on Windows 11. It demonstrates supervisory software architecture, not hardware SIL/PL safety certification under ISO 13849-1 or IEC 61508.
