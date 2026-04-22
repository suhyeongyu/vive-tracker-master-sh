"""Mock Vive Tracker node for Linux verification.

Publishes fake PoseStamped data with configurable patterns (circular/static)
on the same topics as the real vive_tracker_node.

Coordinate system: OpenVR (+Y up, +X right, -Z forward)
Quaternion order: xyzw (ROS standard)
"""

import math

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from scipy.spatial.transform import Rotation


class MockTrackerNode(Node):
    def __init__(self):
        super().__init__("mock_tracker_node")

        self.declare_parameter("publish_rate", 100.0)
        self.declare_parameter("num_trackers", 2)
        self.declare_parameter("pattern", "circular")
        self.declare_parameter("radius", 0.5)
        self.declare_parameter("frame_id", "openvr")

        rate = self.get_parameter("publish_rate").value
        self.num_trackers = self.get_parameter("num_trackers").value
        self.pattern = self.get_parameter("pattern").value
        self.radius = self.get_parameter("radius").value
        self.frame_id = self.get_parameter("frame_id").value

        self.tracker_publishers = []
        for i in range(self.num_trackers):
            pub = self.create_publisher(PoseStamped, f"/vive/tracker_{i}/pose", 10)
            self.tracker_publishers.append(pub)

        self.timer = self.create_timer(1.0 / rate, self.timer_callback)
        self.start_time = self.get_clock().now()

        self.get_logger().info(
            f"MockTracker started: {self.num_trackers} trackers, "
            f"{rate}Hz, pattern={self.pattern}"
        )

    def timer_callback(self):
        now = self.get_clock().now()
        elapsed = (now - self.start_time).nanoseconds / 1e9

        for i, pub in enumerate(self.tracker_publishers):
            msg = PoseStamped()
            msg.header.stamp = now.to_msg()
            msg.header.frame_id = self.frame_id

            if self.pattern == "circular":
                angle = elapsed * 0.5 + i * (2 * math.pi / self.num_trackers)
                msg.pose.position.x = self.radius * math.cos(angle)
                msg.pose.position.y = 1.0
                msg.pose.position.z = self.radius * math.sin(angle)

                quat_xyzw = Rotation.from_euler("y", -angle).as_quat()
                msg.pose.orientation.x = quat_xyzw[0]
                msg.pose.orientation.y = quat_xyzw[1]
                msg.pose.orientation.z = quat_xyzw[2]
                msg.pose.orientation.w = quat_xyzw[3]
            else:  # static
                msg.pose.position.x = float(i) * 0.3
                msg.pose.position.y = 1.0
                msg.pose.position.z = 0.0
                msg.pose.orientation.w = 1.0

            pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MockTrackerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
