"""Launch mock tracker + visualizer for Linux verification."""

import os

from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    config = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "tracker_params.yaml",
    )

    return LaunchDescription(
        [
            ExecuteProcess(
                cmd=[
                    "python",
                    "src/vive_tracker/mock_tracker_node.py",
                    "--ros-args",
                    "--params-file",
                    config,
                ],
                name="mock_tracker",
                output="screen",
            ),
            ExecuteProcess(
                cmd=[
                    "python",
                    "src/vive_tracker/tracker_visualizer_node.py",
                    "--ros-args",
                    "--params-file",
                    config,
                ],
                name="tracker_visualizer",
                output="screen",
            ),
        ]
    )
