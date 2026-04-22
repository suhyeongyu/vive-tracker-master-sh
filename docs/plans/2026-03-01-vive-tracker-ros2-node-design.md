# Vive Tracker ROS 2 Node Design

## Overview

Vive Ultimate Tracker의 6D pose를 ROS 2 PoseStamped topic으로 publish하는 노드 설계.
Windows에서 실행하며, Linux에서는 mock node로 검증.

## Device

- HTC Vive Ultimate Tracker

## Architecture

```
[Windows: SteamVR + ViveHub + ROS 2 Node] -- DDS --> [Linux: ROS 2 Subscriber]
```

## Decisions

| 항목 | 결정 | 이유 |
|------|------|------|
| Approach | rclpy 단일 패키지 | 기존 Python 코드 재활용, 빠른 구현 |
| Topic 구조 | PoseStamped per tracker | 독립 subscribe 가능, ROS 표준 패턴 |
| TF broadcast | 제거 | OpenVR 좌표계와 ROS REP 103 혼용 방지 |
| 좌표계 | OpenVR 원본 (+Y up, +X right, -Z forward) | rrc ViveLeader와 호환 |
| Quaternion | xyzw (ROS PoseStamped 표준) | ROS msg 규격 준수. rrc 소비 시 wxyz 재배열 |
| Publish rate | ~100Hz | 로봇 제어에 적합한 빈도 |
| Tracker 구분 | tracker_0, tracker_1 (OpenVR 발견 순서) | 단순하고 일관된 네이밍 |
| frame_id | "openvr" | 좌표계 convention을 명시적으로 표현 |

## Topics

```
/vive/tracker_0/pose  [geometry_msgs/PoseStamped]
/vive/tracker_1/pose  [geometry_msgs/PoseStamped]
...
```

## Project Structure

```
vive-tracker-test/
├── pixi.toml
├── CLAUDE.md
├── src/
│   └── vive_tracker/
│       ├── __init__.py
│       ├── vive_tracker_node.py      # OpenVR → ROS 2 publish (Windows)
│       ├── mock_tracker_node.py      # 가짜 pose → ROS 2 publish (Linux 검증)
│       └── tracker_listener_node.py  # Subscribe + 로깅 (양쪽)
├── config/
│   └── tracker_params.yaml
├── launch/
│   ├── tracker.launch.py             # Windows 실행용
│   └── mock.launch.py                # Linux 검증용
└── docs/
    └── plans/
```

## Node Specifications

### 1. vive_tracker_node (Windows)

- OpenVR 초기화 (`VRApplication_Other`)
- 100Hz timer callback
- `getDeviceToAbsoluteTrackingPose` → `GenericTracker` 필터링
- 3x4 행렬 → position(xyz) + quaternion(xyzw) 변환
- tracker 발견 순서대로 tracker_0, tracker_1 할당
- 각 tracker마다 `/vive/tracker_{n}/pose` publish

### 2. mock_tracker_node (Linux 검증)

- vive_tracker_node와 동일한 topic 구조로 publish
- 파라미터:
  - `num_trackers` (default: 2)
  - `publish_rate` (default: 100.0)
  - `pattern`: "circular" | "static"
  - `radius` (default: 0.5m)
- circular: 원형 궤적으로 움직이는 가짜 pose 생성
- static: 고정 위치 pose 생성

### 3. tracker_listener_node (양쪽)

- `/vive/tracker_*/pose` subscribe
- 수신 데이터 position, orientation, Hz 로깅
- 검증 목적

## Parameters (tracker_params.yaml)

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
```

## rrc Compatibility

- rrc `PoseData`는 quaternion wxyz, 본 노드는 ROS 표준 xyzw로 publish
- rrc subscriber에서 변환: `q_wxyz = [msg.orientation.w, msg.orientation.x, msg.orientation.y, msg.orientation.z]`
- 좌표계는 OpenVR 그대로이므로 rrc ViveLeader와 동일한 공간에서 동작

## Linux Verification Scenario

1. `pixi run ros2 launch vive_tracker mock.launch.py` 실행
2. `ros2 topic hz /vive/tracker_0/pose` → 100Hz 확인
3. `ros2 topic echo /vive/tracker_0/pose` → pose 데이터 확인
4. tracker_listener_node 로그로 데이터 무결성 확인

## Environment

- pixi + robostack-humble
- ROS 2 Humble
- Platforms: linux-64, win-64
