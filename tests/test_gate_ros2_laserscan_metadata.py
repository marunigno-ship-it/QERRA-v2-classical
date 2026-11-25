# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""Phase 3A & 3B: unit and callback-level tests for LaserScan metadata & REP-117 bounds.

Pure stdlib unittest. LaserScan messages are duck-typed with SimpleNamespace, and
QerraGateNode is loaded under a private name with stub ROS 2 modules (mirroring
test_gate_ros2_odom.py) so both validate_laserscan_metadata() and the real
QerraGateNode._scan_callback / _tick_callback execute identically on Windows.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# Ensure repository root is on sys.path when run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ros2 import qerra_gate_node as node_mod  # noqa: E402

EXPECTED_N = 682
EXPECTED_FOV = 4.1887902  # 240 degrees


def _validate(msg, expected_n=EXPECTED_N, expected_fov=EXPECTED_FOV, **kwargs):
    fn = node_mod.validate_laserscan_metadata
    return fn(msg, expected_n, expected_fov, **kwargs)


def make_header(frame_id="laser", sec=10, nanosec=500_000_000):
    return SimpleNamespace(
        frame_id=frame_id,
        stamp=SimpleNamespace(sec=sec, nanosec=nanosec),
    )


def make_scan(*, n=EXPECTED_N, fov=EXPECTED_FOV, center_shift=0.0, **overrides):
    """Valid duck-typed LaserScan. Increment is derived from the bounds (ROS convention)."""
    angle_min = -fov / 2.0 + center_shift
    angle_max = fov / 2.0 + center_shift
    fields = dict(
        angle_min=angle_min,
        angle_max=angle_max,
        angle_increment=(angle_max - angle_min) / (n - 1),
        range_min=0.02,
        range_max=5.6,
        ranges=[3.0] * n,
        header=make_header(),
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


# ----------------------------------------------------------------------------
# Unit Tests: validate_laserscan_metadata()
# ----------------------------------------------------------------------------
class TestLaserScanMetadataValidation(unittest.TestCase):
    """Verifies the 10-point pure-Python LaserScan metadata validator."""

    def assertRejected(self, scan, token, **kwargs):
        ok, reason = _validate(scan, **kwargs)
        self.assertFalse(ok, f"expected rejection with {token!r}, got acceptance")
        self.assertEqual(reason, token)

    def assertAccepted(self, scan, **kwargs):
        ok, reason = _validate(scan, **kwargs)
        self.assertTrue(ok, f"expected acceptance, got reason {reason!r}")
        self.assertIsNone(reason)

    # ------------------------------------------------------------------ accept
    def test_valid_nominal_scan_accepted(self) -> None:
        ok, reason = _validate(make_scan())
        self.assertIs(ok, True)
        self.assertIsNone(reason)

    def test_valid_realistic_hokuyo_geometry_accepted(self) -> None:
        """682 beams at 360/1024 deg: real span ~239.4 deg, inside the FOV tolerance."""
        increment = math.radians(360.0 / 1024.0)
        span = increment * (EXPECTED_N - 1)
        self.assertAccepted(make_scan(fov=span))

    # ---------------------------------------------------- never raises / missing
    def test_garbage_messages_rejected_without_raising(self) -> None:
        for msg in (None, object(), 42, "scan", SimpleNamespace()):
            with self.subTest(msg=repr(msg)):
                self.assertRejected(msg, "metadata_missing")

    def test_each_missing_top_level_attribute_rejected(self) -> None:
        names = ("angle_min", "angle_max", "angle_increment",
                 "range_min", "range_max", "ranges", "header")
        for name in names:
            with self.subTest(missing=name):
                scan = make_scan()
                delattr(scan, name)
                self.assertRejected(scan, "metadata_missing")

    def test_missing_header_subfields_rejected(self) -> None:
        for header in (SimpleNamespace(),
                       SimpleNamespace(frame_id="laser"),
                       SimpleNamespace(stamp=SimpleNamespace(sec=1, nanosec=0)),
                       SimpleNamespace(frame_id="laser", stamp=SimpleNamespace(sec=1))):
            with self.subTest(header=repr(header)):
                self.assertRejected(make_scan(header=header), "metadata_missing")

    # ------------------------------------------------------------ beam count
    def test_beam_count_must_equal_expected(self) -> None:
        self.assertRejected(make_scan(ranges=[1.0] * 500), "beam_count_mismatch")
        self.assertRejected(make_scan(ranges=[]), "beam_count_mismatch")

    def test_unsized_ranges_rejected(self) -> None:
        for ranges in (None, 5):
            with self.subTest(ranges=repr(ranges)):
                self.assertRejected(make_scan(ranges=ranges), "beam_count_mismatch")

    def test_expected_n_parameter_is_honoured(self) -> None:
        self.assertAccepted(make_scan(n=500), expected_n=500)
        self.assertRejected(make_scan(), "beam_count_mismatch", expected_n=500)

    # ------------------------------------------------------------------ stamp
    def test_stamp_must_be_valid_ros_time(self) -> None:
        bad = ((-1, 0), (0, -1), (5, 1_000_000_000), (5, 2_000_000_000),
               (1.5, 0), (5, 0.5), (None, 0), ("1", 0), (True, 0))
        for sec, nanosec in bad:
            with self.subTest(sec=sec, nanosec=nanosec):
                scan = make_scan(header=make_header(sec=sec, nanosec=nanosec))
                self.assertRejected(scan, "stamp_invalid")

    def test_zero_stamp_passes_metadata_check(self) -> None:
        """Pinned: (0, 0) is not a metadata fault. Freshness is judged by Gate Core."""
        self.assertAccepted(make_scan(header=make_header(sec=0, nanosec=0)))

    # --------------------------------------------------------------- frame_id
    def test_frame_id_must_be_non_empty_string(self) -> None:
        for frame_id in ("", "   ", "\t\n", None, 123, b"laser"):
            with self.subTest(frame_id=repr(frame_id)):
                self.assertRejected(make_scan(header=make_header(frame_id=frame_id)),
                                    "frame_id_invalid")

    # -------------------------------------------------------- angle_increment
    def test_angle_increment_must_be_finite_positive_real(self) -> None:
        for value in (0.0, -0.01, math.nan, math.inf, -math.inf, None, "0.01", True):
            with self.subTest(angle_increment=repr(value)):
                self.assertRejected(make_scan(angle_increment=value),
                                    "angle_increment_invalid")

    # ------------------------------------------------------------ angle bounds
    def test_angle_bounds_must_be_finite_and_ordered(self) -> None:
        cases = (
            {"angle_min": math.nan},
            {"angle_max": math.inf},
            {"angle_min": -math.inf},
            {"angle_min": 1.0, "angle_max": -1.0},   # swapped
            {"angle_min": 0.5, "angle_max": 0.5},    # equal
            {"angle_min": None},
            {"angle_max": "2.0"},
        )
        for overrides in cases:
            with self.subTest(overrides=repr(overrides)):
                self.assertRejected(make_scan(**overrides), "angle_bounds_invalid")

    # -------------------------------------------------------------------- FOV
    def test_fov_inside_tolerance_accepted(self) -> None:
        for delta in (-0.08, 0.0, 0.05, 0.08):
            with self.subTest(delta=delta):
                self.assertAccepted(make_scan(fov=EXPECTED_FOV + delta))

    def test_fov_outside_tolerance_rejected(self) -> None:
        for delta in (-0.5, -0.12, 0.12, 0.5):
            with self.subTest(delta=delta):
                self.assertRejected(make_scan(fov=EXPECTED_FOV + delta), "fov_mismatch")

    def test_fov_tolerance_parameter_is_honoured(self) -> None:
        scan = make_scan(fov=EXPECTED_FOV + 0.05)
        self.assertRejected(scan, "fov_mismatch", fov_tolerance_rad=0.01)
        self.assertAccepted(scan, fov_tolerance_rad=0.1)

    # ------------------------------------------- increment vs bounds and count
    def test_angle_increment_must_match_bounds_and_beam_count(self) -> None:
        base = make_scan()
        inc = base.angle_increment
        for factor in (2.0, 0.5):
            with self.subTest(factor=factor):
                self.assertRejected(make_scan(angle_increment=inc * factor),
                                    "angle_increment_inconsistent")
        self.assertRejected(
            make_scan(angle_increment=(EXPECTED_FOV - 3 * inc) / (EXPECTED_N - 1)),
            "angle_increment_inconsistent",
        )

    def test_off_by_one_angle_max_convention_accepted(self) -> None:
        """Some drivers publish angle_max = angle_min + n * increment."""
        self.assertAccepted(make_scan(angle_increment=EXPECTED_FOV / EXPECTED_N))

    # -------------------------------------------------------------- centering
    def test_scan_must_be_centred_on_forward_axis(self) -> None:
        """The corridor filter assumes a symmetric FOV; an off-axis scan mis-projects."""
        for shift in (0.2, -0.2, 1.0):
            with self.subTest(center_shift=shift):
                self.assertRejected(make_scan(center_shift=shift), "scan_not_centered")
        for shift in (0.0, 0.02, -0.02):
            with self.subTest(center_shift=shift):
                self.assertAccepted(make_scan(center_shift=shift))

    def test_center_tolerance_parameter_is_honoured(self) -> None:
        scan = make_scan(center_shift=0.02)  # |angle_min + angle_max| = 0.04
        self.assertAccepted(scan)
        self.assertRejected(scan, "scan_not_centered", center_tolerance_rad=0.01)

    # ----------------------------------------------------------- range limits
    def test_range_limits_must_be_finite_ordered_and_non_negative(self) -> None:
        cases = (
            {"range_min": math.nan},
            {"range_min": math.inf},
            {"range_min": -0.01},
            {"range_max": math.nan},
            {"range_max": math.inf},
            {"range_min": 5.6, "range_max": 5.6},
            {"range_min": 6.0, "range_max": 5.6},
            {"range_min": None},
            {"range_max": "5.6"},
        )
        for overrides in cases:
            with self.subTest(overrides=repr(overrides)):
                self.assertRejected(make_scan(**overrides), "range_limits_invalid")

    def test_zero_range_min_accepted(self) -> None:
        self.assertAccepted(make_scan(range_min=0.0))

    # ---------------------------------------------------------- check ordering
    def test_first_failing_check_decides_the_reason(self) -> None:
        bad_header = make_header(frame_id="")
        self.assertRejected(make_scan(ranges=[1.0] * 500, header=bad_header),
                            "beam_count_mismatch")
        self.assertRejected(make_scan(header=make_header(frame_id="", sec=-1)),
                            "stamp_invalid")
        self.assertRejected(make_scan(angle_increment=0.0, angle_min=math.nan),
                            "angle_increment_invalid")


# ----------------------------------------------------------------------------
# Callback-Level Integration Harness (Executes real QerraGateNode on Windows)
# ----------------------------------------------------------------------------
class _FakeParameter:
    def __init__(self, value):
        self.value = value


class _FakeLogger:
    def __init__(self):
        self.messages = []

    def _log(self, level, msg):
        self.messages.append((level, str(msg)))

    def info(self, msg):
        self._log("info", msg)

    def warn(self, msg):
        self._log("warn", msg)

    def error(self, msg):
        self._log("error", msg)


class _FakeClock:
    def __init__(self):
        self.ns = 0

    def now(self):
        return SimpleNamespace(nanoseconds=self.ns)


class _FakePublisher:
    def __init__(self):
        self.published = []

    def publish(self, msg):
        self.published.append(msg)


class _FakeNode:
    PARAM_OVERRIDES = {"hsr_source": "none", "hsr_required": False}

    def __init__(self, name):
        self._fake_name = name
        self._fake_params = {}
        self._fake_clock = _FakeClock()
        self._fake_logger = _FakeLogger()

    def declare_parameter(self, name, default=None):
        self._fake_params[name] = self.PARAM_OVERRIDES.get(name, default)

    def get_parameter(self, name):
        return _FakeParameter(self._fake_params[name])

    def get_clock(self):
        return self._fake_clock

    def get_logger(self):
        return self._fake_logger

    def get_name(self):
        return self._fake_name

    def create_subscription(self, *args, **kwargs):
        return object()

    def create_publisher(self, *args, **kwargs):
        return _FakePublisher()

    def create_timer(self, *args, **kwargs):
        return object()

    def destroy_node(self):
        return True


class _FakeTwist:
    def __init__(self):
        self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
        self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)


class _FakeString:
    def __init__(self):
        self.data = ""


class _FakeMsgType:
    pass


class _DummySock:
    def close(self) -> None:
        pass


_MISSING = object()


def _module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _load_node_module():
    rclpy_mod = _module("rclpy", ok=lambda: True)
    fakes = {
        "rclpy": rclpy_mod,
        "rclpy.executors": _module("rclpy.executors", ExternalShutdownException=type(
            "ExternalShutdownException", (Exception,), {})),
        "rclpy.node": _module("rclpy.node", Node=_FakeNode),
        "rclpy.qos": _module("rclpy.qos", qos_profile_sensor_data=object()),
        "geometry_msgs": _module("geometry_msgs"),
        "geometry_msgs.msg": _module("geometry_msgs.msg", Twist=_FakeTwist),
        "nav_msgs": _module("nav_msgs"),
        "nav_msgs.msg": _module("nav_msgs.msg", Odometry=_FakeMsgType),
        "sensor_msgs": _module("sensor_msgs"),
        "sensor_msgs.msg": _module("sensor_msgs.msg", LaserScan=_FakeMsgType),
        "std_msgs": _module("std_msgs"),
        "std_msgs.msg": _module("std_msgs.msg", String=_FakeString),
    }
    saved = {name: sys.modules.get(name, _MISSING) for name in fakes}
    sys.modules.update(fakes)
    try:
        spec = importlib.util.spec_from_file_location(
            "qerra_gate_node_laserscan_under_test",
            REPO_ROOT / "ros2" / "qerra_gate_node.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, old in saved.items():
            if old is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
    return module


NODE_UNDER_TEST = _load_node_module()


class TestScanCallbackMetadataEnforcement(unittest.TestCase):
    """
    Executes the real QerraGateNode._scan_callback() and _tick_callback()
    to verify metadata rejection and REP-117 bounds force fail-closed TRIP_SENSOR_INVALID.
    """

    def setUp(self) -> None:
        self.inputs = []
        self.results = []
        real_step = NODE_UNDER_TEST.step

        def spy_step(state, params, inputs):
            self.inputs.append(inputs)
            res = real_step(state, params, inputs)
            self.results.append(res)
            return res

        for patcher in (
            mock.patch.object(NODE_UNDER_TEST, "step", spy_step),
            mock.patch.object(NODE_UNDER_TEST, "send_state", lambda *a, **k: None),
            mock.patch.object(NODE_UNDER_TEST, "create_state_sender", lambda: _DummySock()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _make_node(self):
        node = NODE_UNDER_TEST.QerraGateNode()
        self.addCleanup(node.destroy_node)
        return node

    def _send_twist(self, node, lin_x=0.20, ang_z=0.0):
        msg = SimpleNamespace(
            linear=SimpleNamespace(x=lin_x, y=0.0, z=0.0),
            angular=SimpleNamespace(x=0.0, y=0.0, z=ang_z),
        )
        node._cmd_vel_callback(msg)

    def _drive_to_cruise(self, node, start_us=1_000_000):
        t_us = start_us
        for _ in range(35):
            t_us += 32_000
            node._fake_clock.ns = t_us * 1_000
            self._send_twist(node)
            sec = t_us // 1_000_000
            nanosec = (t_us % 1_000_000) * 1_000
            node._scan_callback(make_scan(header=make_header(sec=sec, nanosec=nanosec)))
            node._tick_callback()

        self.assertEqual(node._state.mode, NODE_UNDER_TEST.Mode.AWAITING_RESET)

        # Operator reset
        t_us += 32_000
        node._fake_clock.ns = t_us * 1_000
        self._send_twist(node)
        sec = t_us // 1_000_000
        nanosec = (t_us % 1_000_000) * 1_000
        node._scan_callback(make_scan(header=make_header(sec=sec, nanosec=nanosec)))
        node._reset_callback(SimpleNamespace(data="operator"))
        node._tick_callback()
        self.assertEqual(node._state.mode, NODE_UNDER_TEST.Mode.RUN)

        # Active cruise tick
        t_us += 32_000
        node._fake_clock.ns = t_us * 1_000
        self._send_twist(node)
        sec = t_us // 1_000_000
        nanosec = (t_us % 1_000_000) * 1_000
        node._scan_callback(make_scan(header=make_header(sec=sec, nanosec=nanosec)))
        node._tick_callback()
        self.assertEqual(self.results[-1].reason, NODE_UNDER_TEST.Reason.PASS)
        self.assertGreater(node._pub_cmd_safe.published[-1].linear.x, 0.15)
        return t_us

    def test_corrupted_metadata_during_cruise_trips_fail_closed(self) -> None:
        bad_cases = [
            ("angle_increment_invalid", {"angle_increment": 0.0}),
            ("scan_not_centered", {"center_shift": 0.5}),
            ("frame_id_invalid", {"header": make_header(frame_id="")}),
            ("fov_mismatch", {"fov": 2.0}),
            ("range_limits_invalid", {"range_min": 6.0, "range_max": 5.0}),
            ("beam_count_mismatch", {"ranges": [3.0] * 100}),
        ]

        for expected_token, scan_overrides in bad_cases:
            with self.subTest(token=expected_token):
                node = self._make_node()
                t_us = self._drive_to_cruise(node)

                t_us += 32_000
                node._fake_clock.ns = t_us * 1_000
                self._send_twist(node)

                if "header" not in scan_overrides:
                    sec = t_us // 1_000_000
                    nanosec = (t_us % 1_000_000) * 1_000
                    scan_overrides["header"] = make_header(sec=sec, nanosec=nanosec)

                bad_scan = make_scan(**scan_overrides)
                node._scan_callback(bad_scan)

                self.assertIsNone(node._latest_ranges)
                self.assertIsNone(node._lidar_stamp_us)
                self.assertIsNone(node._raw_valid_points)

                warn_logs = [m for lvl, m in node._fake_logger.messages if lvl == "warn"]
                self.assertTrue(any(expected_token in m for m in warn_logs), f"Missing {expected_token} in {warn_logs}")

                node._tick_callback()
                res = self.results[-1]
                self.assertEqual(res.state.mode, NODE_UNDER_TEST.Mode.TRIPPED)
                self.assertEqual(res.reason, NODE_UNDER_TEST.Reason.TRIP_SENSOR_INVALID)

                pub_twist = node._pub_cmd_safe.published[-1]
                self.assertEqual(pub_twist.linear.x, 0.0)
                self.assertEqual(pub_twist.angular.z, 0.0)

                pub_state = json.loads(node._pub_state.published[-1].data)
                self.assertEqual(pub_state["mode"], "TRIPPED")
                self.assertEqual(pub_state["reason"], "TRIP_SENSOR_INVALID")

    def test_valid_scan_restores_sensor_validity_after_bad_metadata(self) -> None:
        node = self._make_node()
        t_us = self._drive_to_cruise(node)

        t_us += 32_000
        node._fake_clock.ns = t_us * 1_000
        self._send_twist(node)
        node._scan_callback(make_scan(angle_increment=-0.01))
        node._tick_callback()
        self.assertEqual(self.results[-1].reason, NODE_UNDER_TEST.Reason.TRIP_SENSOR_INVALID)

        t_us += 32_000
        node._fake_clock.ns = t_us * 1_000
        self._send_twist(node)
        sec = t_us // 1_000_000
        nanosec = (t_us % 1_000_000) * 1_000
        node._scan_callback(make_scan(header=make_header(sec=sec, nanosec=nanosec)))
        node._tick_callback()

        self.assertTrue(self.results[-1].record["lidar_valid"])
        self.assertEqual(self.results[-1].reason, NODE_UNDER_TEST.Reason.LATCHED_DWELL)

    def test_forward_below_range_min_triggers_sensor_invalid_in_callback(self) -> None:
        """REP-117: Forward-corridor reading < range_min trips TRIP_SENSOR_INVALID."""
        node = self._make_node()
        t_us = self._drive_to_cruise(node)

        t_us += 32_000
        node._fake_clock.ns = t_us * 1_000
        self._send_twist(node)
        sec = t_us // 1_000_000
        nanosec = (t_us % 1_000_000) * 1_000

        ranges = [3.0] * EXPECTED_N
        ranges[EXPECTED_N // 2] = 0.01  # Below range_min=0.05 in forward corridor
        scan = make_scan(
            range_min=0.05,
            range_max=5.6,
            ranges=ranges,
            header=make_header(sec=sec, nanosec=nanosec),
        )
        node._scan_callback(scan)
        node._tick_callback()

        res = self.results[-1]
        self.assertEqual(res.state.mode, NODE_UNDER_TEST.Mode.TRIPPED)
        self.assertEqual(res.reason, NODE_UNDER_TEST.Reason.TRIP_SENSOR_INVALID)
        pub_twist = node._pub_cmd_safe.published[-1]
        self.assertEqual(pub_twist.linear.x, 0.0)
        self.assertEqual(pub_twist.angular.z, 0.0)

    def test_above_range_max_garbage_scan_triggers_sensor_invalid_in_callback(self) -> None:
        """REP-117: Scan flooded with > range_max readings drops liveness to 0 -> TRIP_SENSOR_INVALID."""
        node = self._make_node()
        t_us = self._drive_to_cruise(node)

        t_us += 32_000
        node._fake_clock.ns = t_us * 1_000
        self._send_twist(node)
        sec = t_us // 1_000_000
        nanosec = (t_us % 1_000_000) * 1_000

        scan = make_scan(
            range_min=0.05,
            range_max=5.6,
            ranges=[999.0] * EXPECTED_N,  # All beams strictly > range_max
            header=make_header(sec=sec, nanosec=nanosec),
        )
        node._scan_callback(scan)
        self.assertEqual(node._raw_valid_points, 0)
        node._tick_callback()

        res = self.results[-1]
        self.assertEqual(res.state.mode, NODE_UNDER_TEST.Mode.TRIPPED)
        self.assertEqual(res.reason, NODE_UNDER_TEST.Reason.TRIP_SENSOR_INVALID)
        pub_twist = node._pub_cmd_safe.published[-1]
        self.assertEqual(pub_twist.linear.x, 0.0)
        self.assertEqual(pub_twist.angular.z, 0.0)


if __name__ == "__main__":
    unittest.main()
