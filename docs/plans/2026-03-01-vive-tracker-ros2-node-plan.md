# Vive Tracker ROS 2 Node Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Vive Ultimate Tracker의 6D pose를 ROS 2 PoseStamped로 publish하는 노드 패키지를 구현하고, Linux에서 mock node로 검증한다.

**Architecture:** rclpy 기반 단일 Python 패키지. OpenVR 좌표계(+Y up, +X right, -Z forward)를 그대로 PoseStamped로 publish. mock node가 동일한 topic 구조를 제공하여 Linux에서 전체 파이프라인을 검증.

**Tech Stack:** ROS 2 Humble (robostack-humble via pixi), rclpy, geometry_msgs, numpy, scipy, openvr (Windows only)

**Reference files:**
- `track_viser.py` — OpenVR pose 읽기 패턴 (`get_pose_matrix`, `getDeviceToAbsoluteTrackingPose`)
- `references/rrc/rrc/leaders/vive_leader.py` — rrc 호환 pose 구조
- `references/rrc/rrc/core/leader_types.py` — PoseData(position, orientation wxyz)

---

### Task 1: Package scaffold — `__init__.py` + `pixi.toml` update

**Files:**
- Create: `src/vive_tracker/__init__.py`
- Modify: `pixi.toml` — add numpy, scipy deps

**Step 1: Create package directory and __init__.py**

```python
# src/vive_tracker/__init__.py
```

Empty file. Just marks this as a Python package.

**Step 2: Add numpy and scipy to pixi.toml**

Add to `[dependencies]` section:
```toml
numpy = "*"
scipy = "*"
```

**Step 3: Verify pixi resolves**

Run: `pixi lock`
Expected: lockfile updates without errors

**Step 4: Commit**

```bash
git add src/vive_tracker/__init__.py pixi.toml pixi.lock
git commit -m "feat: scaffold vive_tracker package"
```

---

### Task 2: Implement `mock_tracker_node.py`

This comes before vive_tracker_node because it's testable on Linux without hardware.

**Files:**
- Create: `src/vive_tracker/mock_tracker_node.py`

**Step 1: Write the mock tracker node**

```python
"""Mock Vive Tracker node for Linux verification.

Publishes fake PoseStamped data with configurable patterns (circular/static)
on the same topics as the real vive_tracker_node.

Coordinate system: OpenVR (+Y up, +X right, -Z forward)
Quaternion order: xyzw (ROS standard)
"""

import math

import numpy as np
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

        self.publishers = []
        for i in range(self.num_trackers):
            pub = self.create_publisher(PoseStamped, f"/vive/tracker_{i}/pose", 10)
            self.publishers.append(pub)

        self.timer = self.create_timer(1.0 / rate, self.timer_callback)
        self.start_time = self.get_clock().now()

        self.get_logger().info(
            f"MockTracker started: {self.num_trackers} trackers, "
            f"{rate}Hz, pattern={self.pattern}"
        )

    def timer_callback(self):
        now = self.get_clock().now()
        elapsed = (now - self.start_time).nanoseconds / 1e9

        for i, pub in enumerate(self.publishers):
            msg = PoseStamped()
            msg.header.stamp = now.to_msg()
            msg.header.frame_id = self.frame_id

            if self.pattern == "circular":
                angle = elapsed * 0.5 + i * (2 * math.pi / self.num_trackers)
                # OpenVR coords: X right, Y up, Z back
                msg.pose.position.x = self.radius * math.cos(angle)
                msg.pose.position.y = 1.0  # 1m height
                msg.pose.position.z = self.radius * math.sin(angle)

                # Rotate around Y axis to face movement direction
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
```

**Step 2: Smoke test — run the node**

Run: `pixi run ros2 run --prefix-path . -- python3 src/vive_tracker/mock_tracker_node.py`

If ros2 run doesn't work as a standalone script, run directly:
```bash
pixi run python src/vive_tracker/mock_tracker_node.py
```

Expected: Node starts, prints "MockTracker started: 2 trackers, 100.0Hz, pattern=circular"

**Step 3: Verify topic output (in a second terminal)**

Run: `pixi run ros2 topic list`
Expected: `/vive/tracker_0/pose` and `/vive/tracker_1/pose` appear

Run: `pixi run ros2 topic hz /vive/tracker_0/pose`
Expected: ~100Hz

**Step 4: Commit**

```bash
git add src/vive_tracker/mock_tracker_node.py
git commit -m "feat: add mock tracker node for Linux verification"
```

---

### Task 3: Implement `tracker_listener_node.py`

**Files:**
- Create: `src/vive_tracker/tracker_listener_node.py`

**Step 1: Write the listener node**

```python
"""Tracker listener node for verification.

Subscribes to /vive/tracker_*/pose topics and logs position, orientation, and Hz.
"""

import time
from collections import defaultdict, deque

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node


class TrackerListenerNode(Node):
    def __init__(self):
        super().__init__("tracker_listener_node")

        self.declare_parameter("num_trackers", 2)
        num_trackers = self.get_parameter("num_trackers").value

        self._hz_data = defaultdict(lambda: deque(maxlen=100))
        self._last_time = {}

        for i in range(num_trackers):
            topic = f"/vive/tracker_{i}/pose"
            self.create_subscription(
                PoseStamped, topic, lambda msg, idx=i: self._callback(msg, idx), 10
            )
            self.get_logger().info(f"Subscribed to {topic}")

        self.create_timer(1.0, self._log_status)

    def _callback(self, msg: PoseStamped, tracker_idx: int):
        now = time.monotonic()
        if tracker_idx in self._last_time:
            dt = now - self._last_time[tracker_idx]
            if dt > 0:
                self._hz_data[tracker_idx].append(dt)
        self._last_time[tracker_idx] = now

    def _log_status(self):
        for idx in sorted(self._last_time.keys()):
            dts = self._hz_data[idx]
            if dts:
                avg_hz = 1.0 / (sum(dts) / len(dts))
            else:
                avg_hz = 0.0
            self.get_logger().info(f"tracker_{idx}: {avg_hz:.1f} Hz")


def main(args=None):
    rclpy.init(args=args)
    node = TrackerListenerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

**Step 2: Test with mock node running**

Terminal 1: `pixi run python src/vive_tracker/mock_tracker_node.py`
Terminal 2: `pixi run python src/vive_tracker/tracker_listener_node.py`

Expected: Listener logs `tracker_0: ~100.0 Hz` and `tracker_1: ~100.0 Hz` every second.

**Step 3: Commit**

```bash
git add src/vive_tracker/tracker_listener_node.py
git commit -m "feat: add tracker listener node for verification"
```

---

### Task 4: Implement `vive_tracker_node.py`

**Files:**
- Create: `src/vive_tracker/vive_tracker_node.py`

**Step 1: Write the OpenVR tracker node**

```python
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

        # OpenVR init
        try:
            self.vr_system = openvr.init(openvr.VRApplication_Other)
            self.get_logger().info("OpenVR initialized")
        except openvr.OpenVRError as e:
            self.get_logger().fatal(f"OpenVR init failed: {e}")
            raise SystemExit(1)

        # tracker_index -> (publisher, tracker_name)
        self._tracker_map: dict[int, tuple] = {}
        self._next_tracker_id = 0

        self.timer = self.create_timer(1.0 / rate, self.timer_callback)
        self.get_logger().info(f"ViveTracker node started at {rate}Hz")

    def _get_or_create_publisher(self, device_index: int):
        """Lazily create publisher for newly discovered tracker."""
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

            # Convert 3x4 OpenVR matrix to 4x4
            m = np.eye(4)
            for row in range(3):
                for col in range(4):
                    m[row, col] = pose.mDeviceToAbsoluteTracking[row][col]

            # Extract position and quaternion (xyzw for ROS)
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
```

**Step 2: Code review — verify pose conversion matches rrc pattern**

Compare with `track_viser.py:8-13` (`get_pose_matrix`) and
`references/rrc/rrc/leaders/vive_leader.py:249-253` (`_extract_pose`).
Ensure the 3x4 → 4x4 matrix conversion is identical.

**Step 3: Commit**

Note: This node cannot be tested on Linux (requires OpenVR/SteamVR). Testing happens on Windows.

```bash
git add src/vive_tracker/vive_tracker_node.py
git commit -m "feat: add vive tracker node for OpenVR pose publishing"
```

---

### Task 5: Config and launch files

**Files:**
- Create: `config/tracker_params.yaml`
- Create: `launch/mock.launch.py`
- Create: `launch/tracker.launch.py`

**Step 1: Write tracker_params.yaml**

```yaml
vive_tracker_node:
  ros__parameters:
    publish_rate: 100.0
    frame_id: "openvr"

mock_tracker_node:
  ros__parameters:
    publish_rate: 100.0
    num_trackers: 2
    pattern: "circular"
    radius: 0.5
    frame_id: "openvr"

tracker_listener_node:
  ros__parameters:
    num_trackers: 2
```

**Step 2: Write mock.launch.py**

```python
"""Launch mock tracker + listener for Linux verification."""

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
                cmd=["python3", "src/vive_tracker/mock_tracker_node.py",
                     "--ros-args", "--params-file", config],
                name="mock_tracker",
                output="screen",
            ),
            ExecuteProcess(
                cmd=["python3", "src/vive_tracker/tracker_listener_node.py",
                     "--ros-args", "--params-file", config],
                name="tracker_listener",
                output="screen",
            ),
        ]
    )
```

**Step 3: Write tracker.launch.py**

```python
"""Launch real vive tracker node + listener (Windows)."""

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
                cmd=["python3", "src/vive_tracker/vive_tracker_node.py",
                     "--ros-args", "--params-file", config],
                name="vive_tracker",
                output="screen",
            ),
            ExecuteProcess(
                cmd=["python3", "src/vive_tracker/tracker_listener_node.py",
                     "--ros-args", "--params-file", config],
                name="tracker_listener",
                output="screen",
            ),
        ]
    )
```

**Step 4: Test mock launch**

Run: `pixi run ros2 launch launch/mock.launch.py`

Expected: Both nodes start, listener logs ~100Hz per tracker.

**Step 5: Commit**

```bash
git add config/tracker_params.yaml launch/mock.launch.py launch/tracker.launch.py
git commit -m "feat: add config and launch files"
```

---

### Task 6: Update CLAUDE.md and pixi.toml tasks

**Files:**
- Modify: `CLAUDE.md`
- Modify: `pixi.toml` — add pixi tasks for convenient execution

**Step 1: Add pixi tasks to pixi.toml**

Add after `[target.win-64.dependencies]`:

```toml
[tasks]
mock = "python src/vive_tracker/mock_tracker_node.py"
listen = "python src/vive_tracker/tracker_listener_node.py"
track = "python src/vive_tracker/vive_tracker_node.py"
launch-mock = "ros2 launch launch/mock.launch.py"
launch-track = "ros2 launch launch/tracker.launch.py"
```

**Step 2: Update CLAUDE.md with usage info**

Add to end of CLAUDE.md:

```markdown
## Usage

### Linux (verification with mock data)

```bash
pixi run launch-mock        # mock publisher + listener
pixi run mock               # mock publisher only
pixi run listen             # listener only
```

### Windows (real tracker)

```bash
pixi run launch-track       # tracker + listener
pixi run track              # tracker only
```

## Topic Structure

- `/vive/tracker_0/pose` — `geometry_msgs/PoseStamped` (OpenVR coords, quat xyzw)
- `/vive/tracker_1/pose` — ...
```

**Step 3: Verify pixi tasks work**

Run: `pixi run mock` (Ctrl+C after a few seconds)
Expected: Mock node starts normally.

**Step 4: Commit**

```bash
git add CLAUDE.md pixi.toml
git commit -m "feat: add pixi tasks and update CLAUDE.md"
```

---

### Task 7: End-to-end verification on Linux

**Step 1: Run full mock launch**

Run: `pixi run launch-mock`

Expected:
- mock_tracker_node starts, publishes 2 trackers at ~100Hz
- tracker_listener_node starts, logs Hz for each tracker

**Step 2: Verify topics from another terminal**

```bash
pixi run ros2 topic list
# Expected: /vive/tracker_0/pose, /vive/tracker_1/pose

pixi run ros2 topic echo /vive/tracker_0/pose --once
# Expected: PoseStamped with frame_id "openvr", changing position values

pixi run ros2 topic hz /vive/tracker_0/pose
# Expected: ~100Hz
```

**Step 3: Verify message content is rrc-compatible**

Check that the echoed message has:
- `header.frame_id`: "openvr"
- `pose.position`: x, y, z values (Y ~1.0 for height)
- `pose.orientation`: valid quaternion (x² + y² + z² + w² ≈ 1.0)

**Step 4: Remove tf2-ros from pixi.toml (no longer needed)**

Since we removed TF broadcast, `ros-humble-tf2-ros` is unused. Remove it from `[dependencies]`.

**Step 5: Commit**

```bash
git add pixi.toml pixi.lock
git commit -m "chore: remove unused tf2-ros dependency"
```
