# Vive Tracker Test

HTC Vive Ultimate Tracker의 6D pose + velocity + 상태 정보를 Windows에서 ROS 2로 publish하는 시스템.

## Architecture

```
┌─────────────────────────────────────────┐
│              Windows PC                 │
│                                         │
│  Vive Ultimate Tracker                  │
│         │                               │
│         ▼                               │
│  SteamVR + ViveHub                      │
│         │                               │
│         ▼                               │
│  [1] preflight_win.py                   │
│      - 방화벽/SteamVR/트래커 연결 검증  │
│      - 통과 시에만 (2) 실행             │
│         │                               │
│         ▼                               │
│  [2] vive_tracker_node2.py              │
│      (OpenVR → ROS 2 publish)           │
│                                         │
│  /vive/tracker_N/odom                   │   ─── DDS (unicast, CycloneDDS) ──►
│  /vive/tracker_N/pose                   │
│  /vive/tracker_N/diagnostics            │
│  /vive/tracker_N/battery                │
└─────────────────────────────────────────┘
```

SteamVR + ViveHub로 Vive Ultimate Tracker의 상태를 OpenVR로 획득 → preflight 검증 후 ROS 2 노드가 4종 토픽을 100Hz로 publish. DDS를 통해 동일 네트워크의 다른 PC에서 subscribe 가능.

## Prerequisites

| 소프트웨어 | 역할 |
|---|---|
| [SteamVR](https://store.steampowered.com/app/250820/SteamVR/) | 트래커 6D pose 데이터 제공 |
| [ViveHub](https://www.vive.com/kr/setup/tracker-ultimate/) | 트래커 드라이버, 맵 생성/관리 |
| [pixi](https://pixi.sh/) | 패키지 매니저 (ROS 2 Humble 환경 구성) |

## Setup

### 1. pixi 환경 설치

```bash
pixi install
```

설치되는 주요 의존성: ROS 2 Humble, rclpy, CycloneDDS, numpy, scipy, viser, rich, psutil, openvr(pypi).

### 2. CycloneDDS 설정

Multicast가 차단된 네트워크에서 peer IP를 직접 지정하는 유니캐스트 구성.

[cyclonedds.xml](cyclonedds.xml)의 IP 주소를 환경에 맞게 수정:

```xml
<CycloneDDS>
    <Domain id="any">
        <General>
            <Interfaces>
                <NetworkInterface address="<Windows PC IP>"/>
            </Interfaces>
            <AllowMulticast>false</AllowMulticast>
        </General>
        <Discovery>
            <Peers>
                <Peer address="<Windows PC IP>"/>
                <Peer address="<상대 PC IP>"/>
            </Peers>
            <ParticipantIndex>auto</ParticipantIndex>
        </Discovery>
    </Domain>
</CycloneDDS>
```

[pixi.toml](pixi.toml)의 `[feature.win.activation]`에서 `CYCLONEDDS_URI` 경로를 실제 파일 위치로 맞춘다:

```toml
[feature.win.activation]
env = { RMW_IMPLEMENTATION = "rmw_cyclonedds_cpp", CYCLONEDDS_URI = "C:/path/to/cyclonedds.xml" }
```

### 3. SteamVR Headless 설정

HMD 없이 트래커만 사용하려면 SteamVR null driver를 활성화:

```bash
python configure-steamvr-headless.py
```

### 4. ViveHub에서 맵 생성

1. Wireless Dongle과 트래커를 ViveHub에서 페어링
2. ViveHub에서 SLAM 기반 공간 맵 생성
3. SteamVR을 실행하여 트래커가 인식되는지 확인

## Usage

```bash
# preflight 검증 + 트래커 노드 기동 (권장)
pixi run launch-track

# 트래커 노드만 단독 실행 (검증 생략)
pixi run track
```

`launch-track`은 다음 순서로 동작:
1. **preflight_win.py** 실행 → Windows 방화벽, SteamVR, 트래커 연결 상태를 검사
2. `config/tracker_params.yaml`의 `num_trackers`만큼 모든 트래커가 **연결됨** 상태가 되면 통과
3. 통과 시에만 `vive_tracker_node2.py` 기동 (실패 시 토픽 publish 안 함)

### topic 확인

```bash
pixi shell -e win
ros2 topic list                              # 발행 중인 토픽 목록
ros2 topic hz /vive/tracker_0/odom           # ~100Hz
ros2 topic echo /vive/tracker_0/diagnostics  # 상태 확인
```

## Topic Structure

`vive_tracker_node2`가 트래커별로 4종 토픽을 100Hz로 publish:

| Topic | Type | 내용 |
|---|---|---|
| `/vive/tracker_N/odom` | `nav_msgs/Odometry` | position + orientation + linear/angular velocity |
| `/vive/tracker_N/pose` | `geometry_msgs/PoseStamped` | position + orientation (legacy) |
| `/vive/tracker_N/diagnostics` | `diagnostic_msgs/DiagnosticStatus` | 상태 라벨 + tracking_result, pose_valid, connected 값 |
| `/vive/tracker_N/battery` | `sensor_msgs/BatteryState` | 배터리 % + 충전 상태 (값은 내부적으로 1Hz 갱신) |

- 좌표계: OpenVR (+Y up, +X right, -Z forward)
- Quaternion: xyzw (ROS 표준)
- QoS: `qos_profile_sensor_data` (BEST_EFFORT, KEEP_LAST(1))

### 트래커 상태 분류 (`diagnostics.message`)

| 상태 | 조건 |
|---|---|
| 연결 되지 않음 | `bDeviceIsConnected == False` |
| 동기화중 | `eTrackingResult`가 `Uninitialized` / `Calibrating_*` |
| 범위 벗어남 | `eTrackingResult == Running_OutOfRange` |
| 트래킹 손실 | 기타 pose invalid |
| 연결됨 | `Running_OK` + `bPoseIsValid == True` |

## Configuration

[config/tracker_params.yaml](config/tracker_params.yaml):

```yaml
vive_tracker_node2:           # launch-track이 기동하는 노드
  ros__parameters:
    publish_rate: 100.0       # 모든 토픽 publish rate (Hz)
    battery_refresh_interval: 1.0  # OpenVR에서 배터리 값 새로 읽는 주기 (s)
    rescan_interval: 2.0      # 트래커 hotplug 재탐색 주기 (s)
    frame_id: "openvr"
    num_trackers: 2

vive_tracker_node:            # Richard가 작성한 원본 PoseStamped publisher (pixi run track)
  ros__parameters:
    publish_rate: 100.0
    frame_id: "openvr"
    num_trackers: 2
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ROS_DOMAIN_ID` | `25` | ROS 2 domain (양쪽 PC 동일해야 함) |
| `RMW_IMPLEMENTATION` | `rmw_cyclonedds_cpp` | DDS 구현체 |
| `CYCLONEDDS_URI` | — | CycloneDDS 설정 파일 경로 |

## Project Structure

```
vive-tracker-master-sh/
├── src/vive_tracker/
│   ├── vive_tracker_node2.py      # 메인 publisher (odom + pose + diag + batt)
│   ├── vive_tracker_node.py       # Richard가 작성한 원본 PoseStamped publisher
│   ├── preflight_win.py           # Windows 환경 사전 검증 (방화벽/SteamVR/트래커)
│   ├── summary_dashboard.py       # IP/Wi-Fi/peer 상태 요약 유틸
│   └── rate_limiter.py            # drift 보정 rate limiter (옵션, 미사용)
├── launch/
│   └── tracker.launch.py          # preflight → vive_tracker_node2 체인
├── config/
│   └── tracker_params.yaml        # 노드별 파라미터
├── cyclonedds.xml                 # DDS 유니캐스트 설정
├── pixi.toml                      # 의존성 + task 정의
└── configure-steamvr-headless.py  # SteamVR null driver 활성화 스크립트
```

## Network Troubleshooting

topic이 다른 PC에서 보이지 않을 때:

1. **ROS_DOMAIN_ID 확인**: 양쪽 PC에서 동일한 값인지 확인
2. **CycloneDDS peer IP 확인**: [cyclonedds.xml](cyclonedds.xml)의 IP가 올바른지 확인 (`ipconfig`)
3. **방화벽 확인**: Windows 방화벽에서 UDP 차단 여부 확인 (preflight이 자동 감지)
4. **네트워크 확인**: 두 PC가 같은 서브넷에 있는지 확인
5. **ping 테스트**: 양쪽 PC 간 ping이 되는지 확인

preflight_win.py의 Step 4.5가 자동으로 peer ping + Wi-Fi 상태를 확인해 주니 먼저 `pixi run launch-track` 로그를 확인하면 빠르게 원인 파악 가능.
