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
    odom_topic_arg = DeclareLaunchArgument(
        "odom_topic",
        default_value="/odom",
        description="Input Odometry topic for measured chassis velocity standstill verification",
    )
    hsr_topic_arg = DeclareLaunchArgument(
        "hsr_topic",
        default_value="/hsr/telemetry",
        description="Input topic for Layer 1B reflex telemetry JSON strings (used when hsr_source='topic')",
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
    track_width_m_arg = DeclareLaunchArgument(
        "track_width_m",
        default_value="0.4044",
        description="Wheel track separation width in meters (default: 0.4044m for TIAGo base)",
    )
    wheel_radius_m_arg = DeclareLaunchArgument(
        "wheel_radius_m",
        default_value="0.098",
        description="Drive wheel radius in meters (default: 0.098m for TIAGo base)",
    )
    robot_half_width_m_arg = DeclareLaunchArgument(
        "robot_half_width_m",
        default_value="0.32",
        description="Corridor filter half-width in meters (robot base half-width + margin)",
    )
    lidar_n_expected_arg = DeclareLaunchArgument(
        "lidar_n_expected",
        default_value="682",
        description="Required beam count per scan (e.g. 667 for Webots TIAGo, 682 for Hokuyo URG-04LX)",
    )
    lidar_fov_rad_arg = DeclareLaunchArgument(
        "lidar_fov_rad",
        default_value="4.1887902",
        description="Total LiDAR field-of-view in radians (default: 240 deg = 4.1887902 rad)",
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
    hsr_source_arg = DeclareLaunchArgument(
        "hsr_source",
        default_value="udp",
        description="Layer 1B reflex telemetry source: 'topic', 'udp', or 'none' (obstacle-only mode)",
    )
    hsr_port_arg = DeclareLaunchArgument(
        "hsr_port",
        default_value="5008",
        description="Localhost UDP port for Layer 1B reflex telemetry datagrams (used when hsr_source='udp')",
    )
    hsr_required_arg = DeclareLaunchArgument(
        "hsr_required",
        default_value="true",
        description="Fail-closed trip if Layer 1B reflex telemetry is missing or stale ('true'/'false')",
    )
    standstill_required_arg = DeclareLaunchArgument(
        "standstill_required",
        default_value="false",
        description="Require confirmed physical standstill from /odom before starting calm dwell ('true'/'false')",
    )
    state_port_arg = DeclareLaunchArgument(
        "state_port",
        default_value="5007",
        description="Localhost UDP port for simulation clock echo datagrams",
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
                "track_width_m": ParameterValue(LaunchConfiguration("track_width_m"), value_type=float),
                "wheel_radius_m": ParameterValue(LaunchConfiguration("wheel_radius_m"), value_type=float),
                "robot_half_width_m": ParameterValue(LaunchConfiguration("robot_half_width_m"), value_type=float),
                "lidar_n_expected": ParameterValue(LaunchConfiguration("lidar_n_expected"), value_type=int),
                "lidar_fov_rad": ParameterValue(LaunchConfiguration("lidar_fov_rad"), value_type=float),
                "t_react_ms": ParameterValue(LaunchConfiguration("t_react_ms"), value_type=float),
                "lidar_period_ms": ParameterValue(LaunchConfiguration("lidar_period_ms"), value_type=float),
                "lidar_stale_ms": ParameterValue(LaunchConfiguration("lidar_stale_ms"), value_type=float),
                "hsr_source": ParameterValue(LaunchConfiguration("hsr_source"), value_type=str),
                "hsr_topic": ParameterValue(LaunchConfiguration("hsr_topic"), value_type=str),
                "hsr_port": ParameterValue(LaunchConfiguration("hsr_port"), value_type=int),
                "hsr_required": ParameterValue(LaunchConfiguration("hsr_required"), value_type=bool),
                "standstill_required": ParameterValue(LaunchConfiguration("standstill_required"), value_type=bool),
                "state_port": ParameterValue(LaunchConfiguration("state_port"), value_type=int),
                "flight_log_path": ParameterValue(LaunchConfiguration("flight_log_path"), value_type=str),
            }
        ],
        remappings=[
            ("/cmd_vel", LaunchConfiguration("cmd_vel_in")),
            ("/cmd_vel_safe", LaunchConfiguration("cmd_vel_out")),
            ("/scan", LaunchConfiguration("scan_topic")),
            ("/odom", LaunchConfiguration("odom_topic")),
            ("/hsr/telemetry", LaunchConfiguration("hsr_topic")),
            ("/gate/reset", LaunchConfiguration("reset_topic")),
            ("/gate/state", LaunchConfiguration("state_topic")),
        ],
    )

    return LaunchDescription(
        [
            cmd_vel_in_arg,
            cmd_vel_out_arg,
            scan_topic_arg,
            odom_topic_arg,
            hsr_topic_arg,
            reset_topic_arg,
            state_topic_arg,
            rate_hz_arg,
            track_width_m_arg,
            wheel_radius_m_arg,
            robot_half_width_m_arg,
            lidar_n_expected_arg,
            lidar_fov_rad_arg,
            t_react_ms_arg,
            lidar_period_ms_arg,
            lidar_stale_ms_arg,
            hsr_source_arg,
            hsr_port_arg,
            hsr_required_arg,
            standstill_required_arg,
            state_port_arg,
            flight_log_path_arg,
            qerra_gate_node,
        ]
    )
