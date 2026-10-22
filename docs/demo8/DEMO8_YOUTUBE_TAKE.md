# QERRA Supervisory Gate — Demo 8 YouTube Take Evidence

**Artifact:** QERRA Supervisory Gate (Layer 1 Pure-Function Core v0.3)  
**Execution Date:** 2026-10-21  
**Target Platform:** PAL Robotics TIAGo base (simulated in Webots R2025a, Windows 11 host)  
**Run ID:** DEMO8_VIDEO_1792575455  
**Published Head-Hash Anchor:** 8e67456f4ba4c7a980c75a5805126f4e0b0a7e80af09aa70480bd734aee561cd  
*(Anchored in results/DEMO8_VIDEO_1792575455/ANCHOR.txt; represents tamper-evidence within this repository, not independent third-party attestation).*  
**Audit & Replay Status:** Decision-field replay agreement (actuator commands, trip reasons, states, and event flags) audited across all 2,077 control cycles against the repository anchor.

---

## 1. How to Reproduce and Audit This Run

Run this single command from the repository root:

    python verify_log.py results/DEMO8_VIDEO_1792575455/gate_audit.jsonl --anchor-seq 2076 --anchor-hash 8e67456f4ba4c7a980c75a5805126f4e0b0a7e80af09aa70480bd734aee561cd --replay

Expected result: Replay reconstructs all IEEE 754 float inputs and confirms matching decision fields across all 2,077 cycles with exit code 0.

---

## 2. Audited Control Cycle Metrics

* **Total Simulation Duration:** 66.46 s (2,077 control cycles @ dt = 32 ms)
* **Logged Records:** 2,077 cycles (seq 0 to 2076)
* **Startup State:** `TRIPPED` (`TRIP_PROPOSER_DEAD`) — boots fail-closed
* **Obstacle 1 Trip (Cart):** Swept-corridor range = 341 mm at trip tick vs. 346 mm envelope (d_stop)
* **Reset Refusal (Active Hazard):** `RESET_REJECTED_HAZARD` logged when reset attempted facing the cart
* **Sensor Fault Trip:** `TRIP_SENSOR_INVALID` tripped fail-closed at 128 ms elapsed age
* **Proposer Fault Trip:** `TRIP_PROPOSER_STALE` tripped fail-closed at 128 ms elapsed age
* **Obstacle 2 Trip (Pedestrian):** Swept-corridor range = 342 mm at trip tick vs. 346 mm envelope (d_stop)
* **Unplanned Watchdog Trips:** 0 (process priority mitigation applied)

---

## 3. Critical Measurement Definitions & Disclosures

### A. Sensor Trip Range vs. Standstill Distance
* **341 mm and 342 mm are lidar_min_mm readings at the trip tick:** These figures represent the smallest return recorded by the 240° Hokuyo LiDAR within the 0.64 m swept corridor at the exact cycle the gate commanded 0.0 rad/s.
* **They are not physical standstill distances:** Standstill distance accounts for physical braking coasting after the command is cut. Physical standstill clearance was not isolated as a distinct telemetry field in this run.

### B. Discrete Sampling Dynamics (The 4–5 mm Envelope Difference)
* At cruise speed (196 mm/s), the platform travels approximately 6.27 mm per 32 ms simulation step.
* Because the corridor clearance is evaluated at discrete 32 ms intervals, an obstacle that is clear (e.g., > 346 mm) at tick N will cross the boundary between ticks and be sampled inside the envelope at tick N+1.
* The reported trip readings of 341 mm (5 mm inside envelope) and 342 mm (4 mm inside envelope) represent expected discrete-time sampling crossings, not execution lag or envelope calculation error.

### C. Watchdog Parameters and 128 ms Trip Origins
* **LiDAR Freshness Threshold (t_stale_us = 96_000):** The gate trips when sensor age strictly exceeds 96 ms. Evaluated at discrete 32 ms ticks, a frozen timestamp reaches an age of exactly 96 ms at tick 3 (not yet > 96 ms); at tick 4, age reaches 128 ms, crossing the threshold and asserting `TRIP_SENSOR_INVALID`.
* **Proposer Watchdog Threshold (t_watch_us = 150_000):** Governs proposer candidate arrival. The sequencer drops proposals at a discrete simulation step; the gate detects missing proposal freshness and asserts `TRIP_PROPOSER_STALE`.

### D. Automated Sequencer Reset Fallback
* Resets following obstacle stops and fault dwells were triggered via the sequencer controller's automated fallback mechanism (`injected_auto_reset_fallback: true` in `manifest.json`).
* This exercises the gate's state machine transitions and recovery contract (`AWAITING_RESET -> RUN`), but does not demonstrate an authenticated human operator recovery procedure.

---

## 4. Engineering Explanations

### A. Proposer Scheduling Mitigation
Localhost UDP communication on Windows 11 experiences thread starvation during Webots 3D rendering passes. Spawning the untrusted proposer process with `subprocess.ABOVE_NORMAL_PRIORITY_CLASS` eliminated scheduling pauses; zero unplanned watchdog trips occurred during this single run (n=1).

### B. Initial LiDAR Range Plateau Geometry (~3.8 m)
Odometry confirms continuous forward translation at 0.197 m/s from t ~ 5 s, ruling out wheel slip. The Webots URG-04LX sensor model has a 5.6 m maximum range. The flat ~3.8 m reading is consistent with floor returns caused by a slight downward pitch of the robot base/sensor mount. The reading remains constant until the cart enters the swept corridor at t ~ 16.5 s, after which reported range decreases at 0.203 m/s against 0.197 m/s odometry. This geometry attribution is an observed correlation and should be confirmed against exact ray-intersection calculations.

---

## 5. Safety Boundaries & Non-Claims

* **Simulation Only:** Conducted in Webots R2025a on a non-real-time Windows 11 host.
* **Unrated Prototype:** This is an unrated research prototype and has not been certified or validated as a safety-related system against the applicable requirements of ISO 13849-1, IEC 61508, or the relevant machinery regulations.
* **Actuator Boundary:** Commands wheel velocity to 0.0 rad/s in software; does not interface with certified hardware emergency stop circuits, certified safety laser scanners, or Safe Torque Off (STO) relays.
