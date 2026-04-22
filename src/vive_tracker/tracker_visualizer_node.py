"""Tracker visualizer node — 3D visualization of tracker poses via viser.

Subscribes to /vive/tracker_*/pose topics and renders each tracker
as a 3D frame with Hz label in a web-based viewer (localhost:8080).

Coordinate system: OpenVR (+Y up, +X right, -Z forward)
"""

import time
from collections import defaultdict, deque

import numpy as np
import rclpy
import viser
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node


class TrackerVisualizerNode(Node):
    def __init__(self):
        super().__init__("tracker_visualizer_node")

        self.declare_parameter("num_trackers", 2)
        self.declare_parameter("viser_port", 8080)

        num_trackers = self.get_parameter("num_trackers").value
        port = self.get_parameter("viser_port").value

        # Viser server
        self._server = viser.ViserServer(host="0.0.0.0", port=port)
        self._server.scene.set_up_direction("+y")
        self._server.scene.add_frame(
            "/world", show_axes=True, axes_length=0.5, axes_radius=0.01
        )

        # Per-tracker state
        self._hz_data = defaultdict(lambda: deque(maxlen=100))
        self._last_time = {}
        self._last_viz_time = {}
        self._frame_handles = {}
        self._label_handles = {}
        self._gui_handles = {}

        self.declare_parameter("viz_rate", 60.0)
        self._viz_interval = 1.0 / self.get_parameter("viz_rate").value

        # Subscribe to each tracker topic
        for i in range(num_trackers):
            topic = f"/vive/tracker_{i}/pose"
            self.create_subscription(
                PoseStamped, topic, lambda msg, idx=i: self._callback(msg, idx), 10
            )
            self.get_logger().info(f"Subscribed to {topic}")

        self.get_logger().info(f"Viser visualizer at http://localhost:{port}")

    def _ensure_scene_handles(self, tracker_idx: int):
        """Create scene handles once per tracker, reuse on subsequent calls."""
        if tracker_idx in self._frame_handles:
            return
        path = f"/trackers/tracker_{tracker_idx}"
        self._frame_handles[tracker_idx] = self._server.scene.add_frame(
            path, show_axes=True, axes_length=0.15
        )
        self._label_handles[tracker_idx] = self._server.scene.add_label(
            f"{path}/label", text=f"tracker_{tracker_idx} | 0.0 Hz"
        )
        with self._server.gui.add_folder(f"Tracker {tracker_idx}"):
            self._gui_handles[tracker_idx] = self._server.gui.add_text(
                "Update Rate", initial_value="Calculating...", disabled=True
            )

    def _callback(self, msg: PoseStamped, tracker_idx: int):
        # Hz tracking (runs at full rate)
        now = time.monotonic()
        if tracker_idx in self._last_time:
            dt = now - self._last_time[tracker_idx]
            if dt > 0:
                self._hz_data[tracker_idx].append(dt)
        self._last_time[tracker_idx] = now

        # Throttle scene updates
        last_viz = self._last_viz_time.get(tracker_idx, 0.0)
        if now - last_viz < self._viz_interval:
            return
        self._last_viz_time[tracker_idx] = now

        self._ensure_scene_handles(tracker_idx)

        dts = self._hz_data[tracker_idx]
        hz = 1.0 / (sum(dts) / len(dts)) if dts else 0.0

        # Extract pose
        p = msg.pose.position
        q = msg.pose.orientation

        # Update scene handles (lightweight property assignment)
        frame = self._frame_handles[tracker_idx]
        frame.wxyz = np.array([q.w, q.x, q.y, q.z])
        frame.position = np.array([p.x, p.y, p.z])

        self._label_handles[tracker_idx].text = (
            f"tracker_{tracker_idx} | {hz:.1f} Hz"
        )
        self._gui_handles[tracker_idx].value = f"{hz:.1f} Hz"


def main(args=None):
    rclpy.init(args=args)
    node = TrackerVisualizerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
