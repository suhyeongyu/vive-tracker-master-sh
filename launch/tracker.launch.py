"""Launch preflight -> vive tracker node chain (Windows).

Preflight validates firewall / SteamVR / trackers / DDS peer reachability.
Only if preflight exits 0, vive_tracker_node starts publishing.

Launch arguments:
  record:=true|false     Enable rosbag recording of all topics (default: false)
  bag_output:=<path>     Output directory for rosbag
                         (default: rosbags/YYYYMMDD_HHMMSS)

Examples:
  ros2 launch launch/tracker.launch.py
  ros2 launch launch/tracker.launch.py record:=true
  ros2 launch launch/tracker.launch.py record:=true bag_output:=my_capture
"""

import os
from datetime import datetime

import yaml

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    LogInfo,
    RegisterEventHandler,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration


def _read_num_trackers(config_path: str) -> int:
    """vive_tracker_node의 num_trackers 파라미터를 yaml에서 추출."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return int(data["vive_tracker_node"]["ros__parameters"]["num_trackers"])


def generate_launch_description():
    config = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "tracker_params.yaml",
    )
    num_trackers = _read_num_trackers(config)

    record_arg = DeclareLaunchArgument(
        "record",
        default_value="false",
        description="Set to 'true' to record all topics with ros2 bag",
    )
    default_bag_output = f"rosbags/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    bag_output_arg = DeclareLaunchArgument(
        "bag_output",
        default_value=default_bag_output,
        description="Output directory for rosbag (used only when record:=true)",
    )

    preflight = ExecuteProcess(
        cmd=[
            "python",
            "src/vive_tracker/preflight_win.py",
            "--num-trackers",
            str(num_trackers),
        ],
        name="preflight",
        output="screen",
    )

    tracker = ExecuteProcess(
        cmd=[
            "python",
            "src/vive_tracker/vive_tracker_node2.py",
            "--ros-args",
            "--params-file",
            config,
        ],
        name="vive_tracker",
        output="screen",
    )

    recorder = ExecuteProcess(
        cmd=[
            "ros2",
            "bag",
            "record",
            "-a",
            "-o",
            LaunchConfiguration("bag_output"),
        ],
        name="rosbag_recorder",
        output="screen",
        condition=IfCondition(LaunchConfiguration("record")),
    )

    def _on_preflight_exit(event, context):
        if event.returncode == 0:
            return [tracker, recorder]
        return [
            LogInfo(
                msg=f"[launch] preflight 실패 (exit {event.returncode}) - tracker 미기동"
            )
        ]

    return LaunchDescription(
        [
            record_arg,
            bag_output_arg,
            preflight,
            RegisterEventHandler(
                OnProcessExit(
                    target_action=preflight,
                    on_exit=_on_preflight_exit,
                )
            ),
        ]
    )
