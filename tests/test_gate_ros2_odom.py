# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""Unit tests for /odom ingestion and the odometry freshness watchdog in qerra_gate_node.

The node module is loaded under a private name with stub ROS 2 modules, so the REAL
QerraGateNode._odom_callback and _tick_callback execute on any host (Windows without
rclpy, or the Linux CI container) with identical behaviour. The stubs are installed in
sys.modules only for the duration of the import and are then restored.
"""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# Ensure repository root is on sys.path when test is run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ----------------------------------------------------------------------------
# Minimal ROS 2 stand-ins (only what qerra_gate_node touches)
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

    def debug(self, msg):
        self._log("debug", msg)


class _FakeTime:
    def __init__(self, nanoseconds):
        self.nanoseconds = nanoseconds


class _FakeClock:
    def __init__(self):
        self.ns = 0

    def now(self):
        return _FakeTime(self.ns)


class _FakePublisher:
    def __init__(self):
        self.published = []

    def publish(self, msg):
        self.published.append(msg)


class _FakeNode:
    """Stand-in for rclpy.node.Node. No networking, no executor."""

    # Obstacle-only configuration so no UDP HSR socket is opened.
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
    """Placeholder message class (only passed to create_subscription)."""


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
    """Import ros2/qerra_gate_node.py under a private name with stub ROS 2 modules."""
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
            "qerra_gate_node_odom_under_test",
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


NODE_MOD = _load_node_module()


def _odom(linear_x, angular_z):
    """Build a duck-typed nav_msgs/Odometry carrying only the body twist."""
    return SimpleNamespace(
        twist=SimpleNamespace(
            twist=SimpleNamespace(
                linear=SimpleNamespace(x=linear_x),
                angular=SimpleNamespace(z=angular_z),
            )
        )
    )


class TestOdomIngestionAndWatchdog(unittest.TestCase):
    """Verifies /odom -> GateInputs.meas_*_urad_s conversion and fail-closed watchdog."""

    def setUp(self) -> None:
        self.inputs = []
        real_step = NODE_MOD.step

        def spy_step(state, params, inputs):
            self.inputs.append(inputs)
            return real_step(state, params, inputs)

        for patcher in (
            mock.patch.object(NODE_MOD, "step", spy_step),
            mock.patch.object(NODE_MOD, "send_state", lambda *a, **k: None),
            mock.patch.object(NODE_MOD, "create_state_sender", lambda: _DummySock()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    # -- helpers ----------------------------------------------------------
    def _make_node(self):
        node = NODE_MOD.QerraGateNode()
        self.addCleanup(node.destroy_node)
        return node

    @staticmethod
    def _set_time_us(node, t_us: int) -> None:
        node._fake_clock.ns = t_us * 1_000

    def _tick_at(self, node, t_us: int):
        """Advance the ROS clock, run one gate tick, return the GateInputs it built."""
        count_before = len(self.inputs)
        self._set_time_us(node, t_us)
        node._tick_callback()
        self.assertFalse(
            node._fault_latch.is_latched,
            f"Tick latched a node fault: {node._fault_latch.fault_reason}",
        )
        self.assertEqual(len(self.inputs), count_before + 1)
        return self.inputs[-1]

    def _send_odom_at(self, node, t_us: int, linear_x, angular_z) -> None:
        self._set_time_us(node, t_us)
        node._odom_callback(_odom(linear_x, angular_z))

    # -- tests ------------------------------------------------------------
    def test_stale_ceiling_is_100_ms(self) -> None:
        """Spec guard: odometry freshness ceiling is 100 ms."""
        self.assertEqual(NODE_MOD.DEFAULT_ODOM_STALE_US, 100_000)

    def test_no_odom_received_yields_none(self) -> None:
        """Before any /odom message, measured speeds are None."""
        node = self._make_node()
        gi = self._tick_at(node, 1_000_000)
        self.assertIsNone(gi.meas_left_urad_s)
        self.assertIsNone(gi.meas_right_urad_s)

    def test_twist_converts_to_integer_wheel_speeds(self) -> None:
        """Body twist becomes integer urad/s wheel speeds inside GateInputs."""
        cases = [
            # (linear_x, angular_z, expected_left, expected_right)
            (0.20, 0.0, 2_040_816, 2_040_816),     # straight cruise
            (0.0, 1.0, -2_063_265, 2_063_265),     # in-place spin
            (0.20, 0.5, 1_009_184, 3_072_449),     # arc
            (0.0, 0.0, 0, 0),                      # standstill
            (-0.20, 0.0, -2_040_816, -2_040_816),  # reverse
        ]
        for lin_x, ang_z, exp_l, exp_r in cases:
            with self.subTest(linear_x=lin_x, angular_z=ang_z):
                node = self._make_node()
                self._send_odom_at(node, 1_000_000, lin_x, ang_z)
                gi = self._tick_at(node, 1_000_000)
                self.assertEqual(gi.meas_left_urad_s, exp_l)
                self.assertEqual(gi.meas_right_urad_s, exp_r)
                self.assertIsInstance(gi.meas_left_urad_s, int)
                self.assertIsInstance(gi.meas_right_urad_s, int)

    def test_freshness_boundary(self) -> None:
        """Age in [0, 100_000] us is fresh; age < 0 or > 100_000 us fails closed to None."""
        cases = [
            (-50_000, False),   # backward clock jump / future-dated: fails closed
            (-1, False),        # 1 us before stamp: fails closed
            (0, True),
            (32_000, True),
            (100_000, True),    # exactly at the ceiling: still fresh (strict >)
            (100_001, False),   # 1 us over: stale
            (500_000, False),
        ]
        for age_us, expect_fresh in cases:
            with self.subTest(age_us=age_us):
                node = self._make_node()
                self._send_odom_at(node, 1_000_000, 0.20, 0.0)
                gi = self._tick_at(node, 1_000_000 + age_us)
                if expect_fresh:
                    self.assertEqual(gi.meas_left_urad_s, 2_040_816)
                    self.assertEqual(gi.meas_right_urad_s, 2_040_816)
                else:
                    self.assertIsNone(gi.meas_left_urad_s)
                    self.assertIsNone(gi.meas_right_urad_s)

    def test_non_finite_twist_fails_closed(self) -> None:
        """NaN/+Inf/-Inf in linear or angular velocity reset measured speeds to None."""
        bad = [float("nan"), float("inf"), float("-inf")]
        for value in bad:
            for field in ("linear", "angular"):
                with self.subTest(value=value, field=field):
                    node = self._make_node()
                    # Establish a valid, fresh measurement first.
                    self._send_odom_at(node, 1_000_000, 0.20, 0.0)
                    gi_ok = self._tick_at(node, 1_000_000)
                    self.assertEqual(gi_ok.meas_left_urad_s, 2_040_816)

                    # Invalid message arrives (fresh in time, bad in content).
                    lin = value if field == "linear" else 0.20
                    ang = value if field == "angular" else 0.0
                    self._send_odom_at(node, 1_032_000, lin, ang)
                    gi_bad = self._tick_at(node, 1_032_000)
                    self.assertIsNone(gi_bad.meas_left_urad_s)
                    self.assertIsNone(gi_bad.meas_right_urad_s)

    def test_malformed_message_fails_closed(self) -> None:
        """A message lacking the twist fields does not crash the node and yields None."""
        node = self._make_node()
        self._send_odom_at(node, 1_000_000, 0.20, 0.0)
        self._set_time_us(node, 1_032_000)
        node._odom_callback(object())
        gi = self._tick_at(node, 1_032_000)
        self.assertIsNone(gi.meas_left_urad_s)
        self.assertIsNone(gi.meas_right_urad_s)

    def test_recovery_after_stale_and_after_invalid(self) -> None:
        """A fresh valid /odom message restores measured speeds after a fail-closed event."""
        node = self._make_node()

        # Valid -> stale -> None
        self._send_odom_at(node, 1_000_000, 0.20, 0.0)
        gi_stale = self._tick_at(node, 1_200_000)
        self.assertIsNone(gi_stale.meas_left_urad_s)
        self.assertIsNone(gi_stale.meas_right_urad_s)

        # Fresh valid message -> values return
        self._send_odom_at(node, 1_200_000, 0.0, 1.0)
        gi_back = self._tick_at(node, 1_232_000)
        self.assertEqual(gi_back.meas_left_urad_s, -2_063_265)
        self.assertEqual(gi_back.meas_right_urad_s, 2_063_265)

        # Invalid -> None
        self._send_odom_at(node, 1_232_000, float("nan"), 0.0)
        gi_bad = self._tick_at(node, 1_264_000)
        self.assertIsNone(gi_bad.meas_left_urad_s)
        self.assertIsNone(gi_bad.meas_right_urad_s)

        # Fresh valid message -> values return again
        self._send_odom_at(node, 1_264_000, 0.20, 0.0)
        gi_final = self._tick_at(node, 1_296_000)
        self.assertEqual(gi_final.meas_left_urad_s, 2_040_816)
        self.assertEqual(gi_final.meas_right_urad_s, 2_040_816)

    def test_backward_clock_jump_fails_closed(self) -> None:
        """Backward time jump (odom_age_us < 0) immediately resets measured speeds to None."""
        node = self._make_node()

        # 1. Establish valid odometry received at t = 1_000_000 us
        self._send_odom_at(node, 1_000_000, 0.20, 0.0)

        # 2. Clock is evaluated backwards at t = 950_000 us (age = -50_000 us)
        gi_backward = self._tick_at(node, 950_000)
        self.assertIsNone(
            gi_backward.meas_left_urad_s,
            "Backward clock jump must fail closed to None on left wheel",
        )
        self.assertIsNone(
            gi_backward.meas_right_urad_s,
            "Backward clock jump must fail closed to None on right wheel",
        )

        # 3. Clock catches up to t = 1_020_000 us (age = +20_000 us, valid and fresh)
        gi_recovered = self._tick_at(node, 1_020_000)
        self.assertEqual(
            gi_recovered.meas_left_urad_s,
            2_040_816,
            "Valid time progression must restore measured wheel speeds",
        )
        self.assertEqual(
            gi_recovered.meas_right_urad_s,
            2_040_816,
            "Valid time progression must restore measured wheel speeds",
        )

        # 4. Another backward jump: clock steps back before stamp to t = 999_999 us (age = -1 us)
        gi_relapse = self._tick_at(node, 999_999)
        self.assertIsNone(
            gi_relapse.meas_left_urad_s,
            "Relapsing to negative age must immediately drop measured speeds",
        )
        self.assertIsNone(
            gi_relapse.meas_right_urad_s,
            "Relapsing to negative age must immediately drop measured speeds",
        )


if __name__ == "__main__":
    unittest.main()
