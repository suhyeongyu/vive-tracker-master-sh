"""Launch preflight -> vive tracker node chain (Windows).

Preflight validates firewall / SteamVR / trackers / DDS peer reachability.
Only if preflight exits 0, vive_tracker_node starts publishing. Visualizer
runs on the Ubuntu side, not here.
"""

import os

import yaml

from launch import LaunchDescription
from launch.actions import ExecuteProcess, LogInfo, RegisterEventHandler
from launch.event_handlers import OnProcessExit


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
            "src/vive_tracker/vive_tracker_node.py",
            "--ros-args",
            "--params-file",
            config,
        ],
        name="vive_tracker",
        output="screen",
    )

    def _on_preflight_exit(event, context):
        if event.returncode == 0:
            return [tracker]
        return [
            LogInfo(
                msg=f"[launch] preflight 실패 (exit {event.returncode}) - tracker 미기동"
            )
        ]

    return LaunchDescription(
        [
            preflight,
            RegisterEventHandler(
                OnProcessExit(
                    target_action=preflight,
                    on_exit=_on_preflight_exit,
                )
            ),
        ]
    )
