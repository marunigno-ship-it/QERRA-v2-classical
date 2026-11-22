^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package qerra_core
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

2.4.2 (2026-11-22)
------------------
* Gate Core v0.5 standstill-qualification contract: added immutable standstill_required (default False) and w_standstill_tol_urad_s (default 50,000 urad/s) parameters to GateParams, plus meas_left_urad_s and meas_right_urad_s fields to GateInputs.
* Fixed Standstill Dwell Trap in Mode.TRIPPED: 1.0 s calm dwell strictly requires confirmed physical standstill (is_at_standstill()) and immediately resets clear_since_us to None if motion is detected mid-dwell.
* ROS 2 Jazzy node odometry ingestion: subscribed to /odom (nav_msgs/msg/Odometry) in QerraGateNode, translating body twist to integer wheel speeds via twist_to_wheel_speeds() with a 100 ms freshness watchdog and clock-regression guard (age < 0 fails closed).
* Declared nav_msgs exec_depend in package.xml and exposed standstill_required and odom_topic launch arguments in launch/qerra_gate.launch.py.
* Wired TIAGo wheel position sensor derivatives (urad/s) into GateInputs in controllers/tiago_supervisory_gate/tiago_supervisory_gate.py with QERRA_STANDSTILL_REQUIRED environment configuration.
* Extended gate/gate_log.py reconstruct_inputs() to deserialize measured wheel speeds with backward-compatible defaults; verified 439/439 Demo 10 flight log cycles replay bit-for-bit.
* Added TestStandstillDwellQualification (4 unit tests) in tests/test_gate_core.py and isolated /odom ingestion tests (7 unit tests) in tests/test_gate_ros2_odom.py; integrated into ros2_jazzy.yml CI workflow.
* Contributors: Marussa Metocharaki

2.4.1 (2026-11-15)
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
* Propagated rate_hz-derived dt_us into get_live_gate_params() in ros2/qerra_gate_node.py so max_tick_gap_us scales cleanly at lower control rates (e.g., 10 Hz).
* Preserved verified HsrReceiver state across Reason.RESET_ACCEPTED in QerraGateNode._tick_callback() to prevent post-reset TRIP_HSR_INVALID races on UDP streams slower than 31.25 Hz.
* Exposed all 14 typed node parameters in launch/qerra_gate.launch.py (adding track_width_m, wheel_radius_m, robot_half_width_m, lidar_fov_rad, and state_port).
* Added 10 Hz dt_us scaling and 40 ms / 50 ms post-reset HSR continuity regression tests, isolated ros2_jazzy.yml CI steps via ROS_DOMAIN_ID and child process reaping, configured SO_RCVBUF in tests/test_adversarial_hsr.py, and updated LIMITATIONS.md and TECHNICAL_BRIEF_ROS2_GATE.md (v1.4.0).
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
