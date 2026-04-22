"""Vive Tracker ROS 2 node (rich) - publishes pose, twist, diagnostics, battery.

Reads Vive Ultimate Tracker state from SteamVR via OpenVR and publishes at 100Hz:
  /vive/tracker_N/odom        nav_msgs/Odometry
  /vive/tracker_N/pose        geometry_msgs/PoseStamped    (legacy)
  /vive/tracker_N/diagnostics diagnostic_msgs/DiagnosticStatus
  /vive/tracker_N/battery     sensor_msgs/BatteryState

Coordinate system: OpenVR (+Y up, +X right, -Z forward)
Quaternion order: xyzw (ROS standard)
"""

from __future__ import annotations

import math
import time

import numpy as np
import rclpy
from diagnostic_msgs.msg import DiagnosticStatus, KeyValue
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.publisher import Publisher
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState

import openvr


_MAP_PENDING_RESULTS = {
    openvr.TrackingResult_Uninitialized,
    openvr.TrackingResult_Calibrating_InProgress,
    openvr.TrackingResult_Calibrating_OutOfRange,
}

_TRACKING_RESULT_LABELS = {
    openvr.TrackingResult_Uninitialized: "Uninitialized",
    openvr.TrackingResult_Calibrating_InProgress: "Calibrating_InProgress",
    openvr.TrackingResult_Calibrating_OutOfRange: "Calibrating_OutOfRange",
    openvr.TrackingResult_Running_OK: "Running_OK",
    openvr.TrackingResult_Running_OutOfRange: "Running_OutOfRange",
    openvr.TrackingResult_Fallback_RotationOnly: "Fallback_RotationOnly",
}

_STATE_LABELS = {
    "disconnected": "연결 되지 않음",
    "syncing": "동기화중",
    "lost": "트래킹 손실",
    "out_of_range": "범위 벗어남",
    "ok": "연결됨",
}

_STATE_LEVEL = {
    "disconnected": DiagnosticStatus.ERROR,
    "lost": DiagnosticStatus.ERROR,
    "syncing": DiagnosticStatus.WARN,
    "out_of_range": DiagnosticStatus.WARN,
    "ok": DiagnosticStatus.OK,
}


def _classify_tracker(pose) -> str:
    """Classify tracker state. Device class is known GenericTracker (cached)."""
    if not pose.bDeviceIsConnected:
        return "disconnected"
    result = int(pose.eTrackingResult)
    if result in _MAP_PENDING_RESULTS:
        return "syncing"
    if result == openvr.TrackingResult_Running_OK:
        return "ok" if pose.bPoseIsValid else "lost"
    if result == openvr.TrackingResult_Running_OutOfRange:
        return "out_of_range"
    return "lost"


def _mat_to_quat_xyzw(R: np.ndarray) -> tuple[float, float, float, float]:
    """3x3 rotation matrix -> (x, y, z, w) quaternion (no scipy)."""
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0.0:
        s = 0.5 / math.sqrt(t + 1.0)
        return (
            (R[2, 1] - R[1, 2]) * s,
            (R[0, 2] - R[2, 0]) * s,
            (R[1, 0] - R[0, 1]) * s,
            0.25 / s,
        )
    if R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        return (
            0.25 * s,
            (R[0, 1] + R[1, 0]) / s,
            (R[0, 2] + R[2, 0]) / s,
            (R[2, 1] - R[1, 2]) / s,
        )
    if R[1, 1] > R[2, 2]:
        s = 2.0 * math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        return (
            (R[0, 1] + R[1, 0]) / s,
            0.25 * s,
            (R[1, 2] + R[2, 1]) / s,
            (R[0, 2] - R[2, 0]) / s,
        )
    s = 2.0 * math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
    return (
        (R[0, 2] + R[2, 0]) / s,
        (R[1, 2] + R[2, 1]) / s,
        0.25 * s,
        (R[1, 0] - R[0, 1]) / s,
    )


def _extract_pose_components(pose) -> tuple[tuple[float, float, float], np.ndarray]:
    """Extract position + 3x3 rotation from OpenVR HmdMatrix34_t."""
    m = pose.mDeviceToAbsoluteTracking
    position = (m[0][3], m[1][3], m[2][3])
    R = np.array(
        [
            [m[0][0], m[0][1], m[0][2]],
            [m[1][0], m[1][1], m[1][2]],
            [m[2][0], m[2][1], m[2][2]],
        ]
    )
    return position, R


class TrackerInfo:
    __slots__ = (
        "name",
        "serial",
        "pub_odom",
        "pub_pose",
        "pub_diag",
        "pub_batt",
        "battery_pct",
        "is_charging",
    )

    def __init__(
        self,
        name: str,
        serial: str,
        pub_odom: Publisher,
        pub_pose: Publisher,
        pub_diag: Publisher,
        pub_batt: Publisher,
    ):
        self.name = name
        self.serial = serial
        self.pub_odom = pub_odom
        self.pub_pose = pub_pose
        self.pub_diag = pub_diag
        self.pub_batt = pub_batt
        self.battery_pct = float("nan")
        self.is_charging = False


class ViveTrackerNode(Node):
    def __init__(self):
        super().__init__("vive_tracker_node2")

        self.declare_parameter("publish_rate", 100.0)
        self.declare_parameter("battery_refresh_interval", 1.0)
        self.declare_parameter("rescan_interval", 2.0)
        self.declare_parameter("frame_id", "openvr")
        self.declare_parameter("num_trackers", 1)

        pub_rate = float(self.get_parameter("publish_rate").value)
        self._battery_refresh_interval = float(
            self.get_parameter("battery_refresh_interval").value
        )
        self._rescan_interval = float(self.get_parameter("rescan_interval").value)
        self.frame_id = self.get_parameter("frame_id").value
        self.num_trackers = int(self.get_parameter("num_trackers").value)

        try:
            self.vr_system = openvr.init(openvr.VRApplication_Other)
            self.get_logger().info("OpenVR initialized")
        except openvr.OpenVRError as e:
            self.get_logger().fatal(f"OpenVR init failed: {e}")
            raise SystemExit(1)

        self._tracker_map: dict[int, TrackerInfo] = {}
        self._next_tracker_id = 0
        self._last_rescan = 0.0
        self._last_battery_read = 0.0

        self._rescan_devices()

        self._timer = self.create_timer(1.0 / pub_rate, self._tick)

        self.get_logger().info(
            f"ViveTracker2 started at {pub_rate}Hz (expecting {self.num_trackers} tracker(s))"
        )

    def _rescan_devices(self):
        """Discover new GenericTracker devices and create their publishers."""
        for i in range(openvr.k_unMaxTrackedDeviceCount):
            if self.vr_system.getTrackedDeviceClass(i) != openvr.TrackedDeviceClass_GenericTracker:
                continue
            if i in self._tracker_map:
                continue
            tracker_name = f"tracker_{self._next_tracker_id}"
            try:
                serial = self.vr_system.getStringTrackedDeviceProperty(
                    i, openvr.Prop_SerialNumber_String
                )
            except openvr.OpenVRError:
                serial = ""
            pub_odom = self.create_publisher(
                Odometry, f"/vive/{tracker_name}/odom", qos_profile_sensor_data
            )
            pub_pose = self.create_publisher(
                PoseStamped, f"/vive/{tracker_name}/pose", qos_profile_sensor_data
            )
            pub_diag = self.create_publisher(
                DiagnosticStatus,
                f"/vive/{tracker_name}/diagnostics",
                qos_profile_sensor_data,
            )
            pub_batt = self.create_publisher(
                BatteryState,
                f"/vive/{tracker_name}/battery",
                qos_profile_sensor_data,
            )
            self._tracker_map[i] = TrackerInfo(
                tracker_name, serial, pub_odom, pub_pose, pub_diag, pub_batt
            )
            self._next_tracker_id += 1
            self.get_logger().info(
                f"Discovered {tracker_name} (serial={serial}, device={i})"
            )

    def _refresh_battery(self):
        """Pull battery % and charging state from OpenVR. Called at ~1Hz from _tick."""
        for device_index, info in self._tracker_map.items():
            try:
                info.battery_pct = float(
                    self.vr_system.getFloatTrackedDeviceProperty(
                        device_index, openvr.Prop_DeviceBatteryPercentage_Float
                    )
                )
                info.is_charging = bool(
                    self.vr_system.getBoolTrackedDeviceProperty(
                        device_index, openvr.Prop_DeviceIsCharging_Bool
                    )
                )
            except openvr.OpenVRError:
                pass  # keep previous cached values

    def _tick(self):
        """100Hz: publish Odometry + PoseStamped + DiagnosticStatus + BatteryState."""
        now_mono = time.monotonic()
        if now_mono - self._last_rescan > self._rescan_interval:
            self._rescan_devices()
            self._last_rescan = now_mono
        if now_mono - self._last_battery_read > self._battery_refresh_interval:
            self._refresh_battery()
            self._last_battery_read = now_mono

        poses = self.vr_system.getDeviceToAbsoluteTrackingPose(
            openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount
        )
        stamp = self.get_clock().now().to_msg()

        for device_index, info in self._tracker_map.items():
            pose = poses[device_index]
            state = _classify_tracker(pose)

            # Odometry + PoseStamped only when pose is valid
            if pose.bPoseIsValid:
                position, R = _extract_pose_components(pose)
                qx, qy, qz, qw = _mat_to_quat_xyzw(R)

                odom = Odometry()
                odom.header.stamp = stamp
                odom.header.frame_id = self.frame_id
                odom.child_frame_id = info.name
                odom.pose.pose.position.x = position[0]
                odom.pose.pose.position.y = position[1]
                odom.pose.pose.position.z = position[2]
                odom.pose.pose.orientation.x = qx
                odom.pose.pose.orientation.y = qy
                odom.pose.pose.orientation.z = qz
                odom.pose.pose.orientation.w = qw
                odom.twist.twist.linear.x = pose.vVelocity[0]
                odom.twist.twist.linear.y = pose.vVelocity[1]
                odom.twist.twist.linear.z = pose.vVelocity[2]
                odom.twist.twist.angular.x = pose.vAngularVelocity[0]
                odom.twist.twist.angular.y = pose.vAngularVelocity[1]
                odom.twist.twist.angular.z = pose.vAngularVelocity[2]
                info.pub_odom.publish(odom)

                pose_msg = PoseStamped()
                pose_msg.header.stamp = stamp
                pose_msg.header.frame_id = self.frame_id
                pose_msg.pose = odom.pose.pose
                info.pub_pose.publish(pose_msg)

            # Diagnostics + Battery published every tick regardless of pose validity
            diag = DiagnosticStatus()
            diag.name = info.name
            diag.hardware_id = info.serial
            diag.level = _STATE_LEVEL.get(state, DiagnosticStatus.ERROR)
            diag.message = _STATE_LABELS.get(state, state)
            diag.values = [
                KeyValue(
                    key="tracking_result",
                    value=_TRACKING_RESULT_LABELS.get(
                        int(pose.eTrackingResult), str(int(pose.eTrackingResult))
                    ),
                ),
                KeyValue(key="pose_valid", value=str(bool(pose.bPoseIsValid))),
                KeyValue(key="connected", value=str(bool(pose.bDeviceIsConnected))),
                KeyValue(key="state", value=state),
            ]
            info.pub_diag.publish(diag)

            batt = BatteryState()
            batt.header.stamp = stamp
            batt.header.frame_id = info.name
            batt.percentage = info.battery_pct
            batt.power_supply_status = (
                BatteryState.POWER_SUPPLY_STATUS_CHARGING
                if info.is_charging
                else BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
            )
            batt.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LIPO
            batt.present = bool(pose.bDeviceIsConnected)
            info.pub_batt.publish(batt)

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
