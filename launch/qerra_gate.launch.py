# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki
"""ROS 2 Jazzy launch file for the QERRA Supervisory Gate Node (Pattern B)."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    # -------------------------------------------------------------------------
    # Topic Remapping Launch Arguments (Pattern B External Integration)
    # -------------------------------------------------------------------------
    cmd_vel_in_arg = DeclareLaunchArgument(
        "cmd_vel_in",
        default_value="/cmd_vel",
        description="Input topic for untrusted velocity proposals (e.g. from Nav2 or teleop)",
    )
    cmd_vel_out_arg = DeclareLaunchArgument(
        "cmd_vel_out",
        default_value="/cmd_vel_safe",
        description="Output topic for verified, fail-closed velocity setpoints to base controller",
    )
    scan_topic_arg = DeclareLaunchArgument(
        "scan_topic",
        default_value="/scan",
        description="Input LaserScan topic (Best Effort QoS)",
    )
    reset_topic_arg = DeclareLaunchArgument(
        "reset_topic",
        default_value="/gate/reset",
        description="Input topic for authorized operator reset requests",
    )
    state_topic_arg = DeclareLaunchArgument(
        "state_topic",
        default_value="/gate/state",
        description="Output topic for JSON diagnostic and flight state telemetry",
    )

    # -------------------------------------------------------------------------
    # Node Configuration Launch Arguments (Strict Typing via ParameterValue)
    # -------------------------------------------------------------------------
    rate_hz_arg = DeclareLaunchArgument(
        "rate_hz",
        default_value="31.25",
        description="Nominal control loop tick frequency in Hz (default: 31.25 Hz / 32 ms dt)",
    )
    t_react_ms_arg = DeclareLaunchArgument(
        "t_react_ms",
        default_value="96.0",
        description="Reaction-time allowance budget for dynamic stopping envelope in milliseconds",
    )
    lidar_period_ms_arg = DeclareLaunchArgument(
        "lidar_period_ms",
        default_value="32.0",
        description="Expected LiDAR scan period in milliseconds (32.0 ms sim, 100.0 ms hardware)",
    )
    lidar_stale_ms_arg = DeclareLaunchArgument(
        "lidar_stale_ms",
        default_value="96.0",
        description="Maximum accepted LiDAR scan age before fail-closed trip (>= 2*period + dt)",
    )
    lidar_n_expected_arg = DeclareLaunchArgument(
        "lidar_n_expected",
        default_value="682",
        description="Required beam count per scan (e.g. 667 for Webots TIAGo, 682 for Hokuyo URG-04LX)",
    )
    hsr_source_arg = DeclareLaunchArgument(
        "hsr_source",
        default_value="udp",
        description="Layer 1B reflex telemetry source: 'udp' or 'none' (obstacle-only mode)",
    )
    hsr_port_arg = DeclareLaunchArgument(
        "hsr_port",
        default_value="5008",
        description="Localhost UDP port for Layer 1B reflex telemetry datagrams",
    )
    hsr_required_arg = DeclareLaunchArgument(
        "hsr_required",
        default_value="true",
        description="Fail-closed trip if Layer 1B reflex telemetry is missing or stale ('true'/'false')",
    )
    flight_log_path_arg = DeclareLaunchArgument(
        "flight_log_path",
        default_value="",
        description="Path for SHA-256 JSONL flight log (empty disables node flight logging)",
    )

    # -------------------------------------------------------------------------
    # Node Execution Configuration
    # -------------------------------------------------------------------------
    qerra_gate_node = Node(
        package="qerra_core",
        executable="qerra_gate_node",
        name="qerra_gate_node",
        output="screen",
        emulate_tty=True,
        parameters=[
            {
                "rate_hz": ParameterValue(LaunchConfiguration("rate_hz"), value_type=float),
                "t_react_ms": ParameterValue(LaunchConfiguration("t_react_ms"), value_type=float),
                "lidar_period_ms": ParameterValue(LaunchConfiguration("lidar_period_ms"), value_type=float),
                "lidar_stale_ms": ParameterValue(LaunchConfiguration("lidar_stale_ms"), value_type=float),
                "lidar_n_expected": ParameterValue(LaunchConfiguration("lidar_n_expected"), value_type=int),
                "hsr_source": ParameterValue(LaunchConfiguration("hsr_source"), value_type=str),
                "hsr_port": ParameterValue(LaunchConfiguration("hsr_port"), value_type=int),
                "hsr_required": ParameterValue(LaunchConfiguration("hsr_required"), value_type=bool),
                "flight_log_path": ParameterValue(LaunchConfiguration("flight_log_path"), value_type=str),
            }
        ],
        remappings=[
            ("/cmd_vel", LaunchConfiguration("cmd_vel_in")),
            ("/cmd_vel_safe", LaunchConfiguration("cmd_vel_out")),
            ("/scan", LaunchConfiguration("scan_topic")),
            ("/gate/reset", LaunchConfiguration("reset_topic")),
            ("/gate/state", LaunchConfiguration("state_topic")),
        ],
    )

    return LaunchDescription(
        [
            cmd_vel_in_arg,
            cmd_vel_out_arg,
            scan_topic_arg,
            reset_topic_arg,
            state_topic_arg,
            rate_hz_arg,
            t_react_ms_arg,
            lidar_period_ms_arg,
            lidar_stale_ms_arg,
            lidar_n_expected_arg,
            hsr_source_arg,
            hsr_port_arg,
            hsr_required_arg,
            flight_log_path_arg,
            qerra_gate_node,
        ]
    )
