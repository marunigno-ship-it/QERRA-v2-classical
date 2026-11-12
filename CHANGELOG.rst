^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package qerra_core
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

2.4.1 (2026-11-12)
------------------
* Standalone ROS 2 Gate Node: packaging, native Jazzy CI, persistent NodeFaultLatch, and single ROS clock domain.
* Nav2 exterior command-interface integration suite (Priority P12) executing under native rclpy in official ros:jazzy container.
* Pattern B topic remapping and launch architecture with strict ParameterValue typing in launch/qerra_gate.launch.py.
* Asynchronous Layer 1B QERRA-HSR perception stream monitor with sticky frozen-frame latching and controlled 5-tick producer-restart rebase dwell.
* Kinematic stopping envelope with symmetrical fail-closed clamping policy (Option A / AR-2) rejecting proposals requiring wheel reversal.
* SHA-256 rolling hash-chained flight recorder (GateLogger) with R-10 fail-closed actuator clamping on write/fsync failure.
* Interoperable LiDAR subscription using qos_profile_sensor_data (Best Effort + Volatile) with dynamic beam mismatch guarding.
* Live dual-protocol integration suite (Priority P10) and live pub/sub topic traffic watchdog suite (Priority P9).
* Complete isolation of qerra_core: decoupled from unreleased message packages, external REST dependencies, and higher-order deliberative layers.
* Contributors: Marussa Metocharaki

2.3.1 (2026-10-31)
------------------
* Asynchronous HSR telemetry ingestion via non-blocking UDP receiver on port 5008 with worst-severity batch reduction.
* Simulation clock echo on UDP port 5007 to synchronize synthetic telemetry producers.
* Lidar beam mismatch fail-closed guard discarding non-conforming scans to trip TRIP_SENSOR_INVALID.
* Configuration contradiction guard rejecting hsr_source="none" when hsr_required=True.
* Live reaction time parameter construction via get_live_gate_params.
* Contributors: Marussa Metocharaki

2.2.1 (2026-10-27)
------------------
* Gate recovery interlock ordering enforcing non-clear HSR validation prior to operator reset acceptance.
* Actuator clamping isolation with independent motor exception handling.
* Synchronized package metadata with repository-wide Apache-2.0 relicensing.
* Monotonic host jitter tracking and execution interval distribution reporting.
* Contributors: Marussa Metocharaki

2.2.0 (2026-10-25)
------------------
* Layer 1B QERRA-HSR reflex arbitration integrated with Layer 1A Supervisory Gate.
* Enforced TRIP_HSR_CRITICAL, TRIP_HSR_INVALID, and TRIP_HSR_STALE discrete cycle trip boundaries.
* Deterministic offline replay extension for HSR flight log streams.
* Pre-registered closed-loop distress reflex stop verification.
* Contributors: Marussa Metocharaki

2.1.0 (2026-10-15)
------------------
* Initial decoupled Supervisory Gate core (gate_core.py v0.3) holding exclusive motor actuator authority.
* Kinematic stopping envelope d_stop(v) bounded by design deceleration and margin.
* Tamper-evident SHA-256 rolling block chain flight recorder (gate_log.py) and standalone auditor (verify_log.py).
* Proposer freshness watchdog (150 ms) and fail-closed latched recovery.
* Automated multi-suite CI with standard-library-only AST validation.
* Contributors: Marussa Metocharaki
