# QERRA Supervisory Gate — Demo 8 YouTube Take Evidence

**Artifact:** QERRA Supervisory Gate (Layer 2 Pure-Function Core v0.3)  
**Execution Date:** 2026-10-21  
**Target Platform:** PAL Robotics TIAGo base (simulated in Webots R2025a, Windows 11 host)  
**Run ID:** DEMO8_VIDEO_1792575455  
**External Head Hash Seal:** 8e67456f4ba4c7a980c75a5805126f4e0b0a7e80af09aa70480bd734aee561cd  
**Log Verification Status:** Audited and verified against anchor file; bit-for-bit replay passed across all 2,077 control cycles.

## 1. Verified Control Cycle Metrics
* Total Simulation Duration: 56.86 s (1,777 ticks @ dt = 32 ms)
* Logged Audit Records: 2,077 cycles (seq 0 to 2076)
* Startup State: TRIPPED (TRIP_PROPOSER_DEAD)
* Obstacle 1 Stop (Cart): Lidar min: 341 mm vs Envelope: 346 mm
* Reset Refusal (Hazard): RESET_REJECTED_HAZARD logged at 38.53 s
* Sensor Fault Trip: TRIP_SENSOR_INVALID tripped fail-closed in 120 ms
* Proposer Fault Trip: TRIP_PROPOSER_STALE tripped fail-closed in 130 ms
* Obstacle 2 Stop (Pedestrian): Lidar min: 342 mm vs Envelope: 346 mm
* Unplanned Watchdog Trips: 0 (Process priority mitigation applied)

## 2. Engineering Explanations
**A. Proposer Scheduling Mitigation:**
The untrusted proposer process was spawned with subprocess.ABOVE_NORMAL_PRIORITY_CLASS to prevent Windows 3D rendering from starving the UDP thread. Zero unplanned trips occurred.

**B. Geometry Explanation for Initial Lidar Range Plateau (~3818 mm):**
Between t=5.76s and 16.32s, the lidar minimum held at ~3817-3821 mm while wheels commanded 2.00 rad/s (196 mm/s). TIAGo starts at x=-3.84m and the cart is at x=+3.00m (6.84m separation). At 196 mm/s, traveling 2.15m required 11.0s. At t=17.28s, TIAGo reached x=-1.69m. The cart entered the 3.82m reliable sensor line-of-sight, and range decreased linearly matching odometry. The robot did not stand still.
