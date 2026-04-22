"""Vive Tracker ROS 2 node — publishes 6D pose via OpenVR.

Reads Vive Ultimate Tracker poses from SteamVR via OpenVR API
and publishes each tracker as PoseStamped.

Coordinate system: OpenVR (+Y up, +X right, -Z forward)
Quaternion order: xyzw (ROS standard)

Requires: SteamVR running, ViveHub connected (Windows)
"""

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from scipy.spatial.transform import Rotation

import openvr


class ViveTrackerNode(Node):
    def __init__(self):
        super().__init__("vive_tracker_node")

        self.declare_parameter("publish_rate", 100.0)
        self.declare_parameter("frame_id", "openvr")

        rate = self.get_parameter("publish_rate").value
        self.frame_id = self.get_parameter("frame_id").value

        try:
            self.vr_system = openvr.init(openvr.VRApplication_Other)
            self.get_logger().info("OpenVR initialized")
        except openvr.OpenVRError as e:
            self.get_logger().fatal(f"OpenVR init failed: {e}")
            raise SystemExit(1)

        self._tracker_map: dict[int, tuple] = {}
        self._next_tracker_id = 0

        self.timer = self.create_timer(1.0 / rate, self.timer_callback)
        self.get_logger().info(f"ViveTracker node started at {rate}Hz")

    def _get_or_create_publisher(self, device_index: int):
        if device_index not in self._tracker_map:
            tracker_name = f"tracker_{self._next_tracker_id}"
            topic = f"/vive/{tracker_name}/pose"
            pub = self.create_publisher(PoseStamped, topic, 10)
            self._tracker_map[device_index] = (pub, tracker_name)
            self._next_tracker_id += 1

            serial = self.vr_system.getStringTrackedDeviceProperty(
                device_index, openvr.Prop_SerialNumber_String
            )
            self.get_logger().info(
                f"Discovered {tracker_name} (serial={serial}, device={device_index})"
            )
        return self._tracker_map[device_index]

    def timer_callback(self):
        poses = self.vr_system.getDeviceToAbsoluteTrackingPose(
            openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount
        )

        now = self.get_clock().now()

        for i in range(openvr.k_unMaxTrackedDeviceCount):
            if self.vr_system.getTrackedDeviceClass(i) != openvr.TrackedDeviceClass_GenericTracker:
                continue

            pose = poses[i]
            if not pose.bPoseIsValid:
                continue

            pub, _ = self._get_or_create_publisher(i)

            m = np.eye(4)
            for row in range(3):
                for col in range(4):
                    m[row, col] = pose.mDeviceToAbsoluteTracking[row][col]

            position = m[:3, 3]
            quat_xyzw = Rotation.from_matrix(m[:3, :3]).as_quat()

            msg = PoseStamped()
            msg.header.stamp = now.to_msg()
            msg.header.frame_id = self.frame_id
            msg.pose.position.x = float(position[0])
            msg.pose.position.y = float(position[1])
            msg.pose.position.z = float(position[2])
            msg.pose.orientation.x = float(quat_xyzw[0])
            msg.pose.orientation.y = float(quat_xyzw[1])
            msg.pose.orientation.z = float(quat_xyzw[2])
            msg.pose.orientation.w = float(quat_xyzw[3])

            pub.publish(msg)

    def destroy_node(self):
        openvr.shutdown()
        self.get_logger().info("OpenVR shutdown")
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ViveTrackerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
