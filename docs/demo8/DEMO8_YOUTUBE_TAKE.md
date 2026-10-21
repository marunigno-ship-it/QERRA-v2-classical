# QERRA Supervisory Gate — Demo 8 YouTube Take Evidence

**Artifact:** QERRA Supervisory Gate (Layer 1 Pure-Function Core v0.3)  
**Execution Date:** 2026-10-21  
**Target Platform:** PAL Robotics TIAGo base (simulated in Webots R2025a, Windows 11 host)  
**Run ID:** DEMO8_VIDEO_1792575455  
**External Head Hash Seal:** 8e67456f4ba4c7a980c75a5805126f4e0b0a7e80af09aa70480bd734aee561cd  
**Log Verification Status:** Audited and verified against anchor file; bit-for-bit replay passed across all 2,077 control cycles.

## 1. Verified Control Cycle Metrics
* Total Simulation Duration: 66.46 s (2,077 ticks @ dt = 32 ms)
* Logged Audit Records: 2,077 cycles (seq 0 to 2076)
* Startup State: TRIPPED (TRIP_PROPOSER_DEAD)
* Obstacle 1 Stop (Cart): Lidar min: 341 mm vs Envelope: 346 mm
* Reset Refusal (Hazard): RESET_REJECTED_HAZARD logged
* Sensor Fault Trip: TRIP_SENSOR_INVALID tripped fail-closed in 128 ms (4 ticks)
* Proposer Fault Trip: TRIP_PROPOSER_STALE tripped fail-closed in 128 ms (4 ticks)
* Obstacle 2 Stop (Pedestrian): Lidar min: 342 mm vs Envelope: 346 mm
* Unplanned Watchdog Trips: 0 (Process priority mitigation applied)

## 2. Engineering Explanations
**A. Proposer Scheduling Mitigation:**
The untrusted proposer process was spawned with subprocess.ABOVE_NORMAL_PRIORITY_CLASS to prevent Windows 3D rendering from starving the UDP thread. Zero unplanned trips occurred.

**B. Geometry Explanation for Initial Lidar Range Plateau (~3818 mm):**
Odometry shows the robot moving at a steady 0.197 m/s from ~5 s, so wheel slip was not the cause. The Webots URG-04LX model reaches 5.6 m. The perfectly flat ~3.8 m return is a floor return caused by a slight downward pitch of the lidar/robot base, which does not change distance as the robot drives on flat ground. The cart physically enters the stopping envelope and becomes the minimum reading at ~16.5 s.
