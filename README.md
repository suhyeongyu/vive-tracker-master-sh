# Vive Tracker Test

HTC Vive Ultimate Tracker의 6D pose 데이터를 Windows에서 ROS 2로 publish하고, Ubuntu에서 subscribe하여 시각화하는 시스템.

## Architecture

```
┌─────────────────────────────────────┐          ┌──────────────────────────────┐
│           Windows PC                │          │         Ubuntu PC            │
│                                     │          │                              │
│  Vive Ultimate Tracker              │          │                              │
│         │                           │          │                              │
│         ▼                           │          │                              │
│  SteamVR + ViveHub                  │   DDS    │                              │
│         │                           │ (unicast)│                              │
│         ▼                           │          │                              │
│  vive_tracker_node.py               │          │                              │
│   (OpenVR API → ROS 2 publish)      ├─────────►│  ros2 topic echo / subscribe │
│                                     │          │  tracker_visualizer_node.py   │
│  /vive/tracker_0/pose  ─────────────┼──────────┼► (viser 3D viewer)           │
│  /vive/tracker_1/pose  ─────────────┼──────────┼►                             │
│  ...                                │          │  http://localhost:8080        │
└─────────────────────────────────────┘          └──────────────────────────────┘
```

- **Windows**: SteamVR + ViveHub를 통해 Vive Ultimate Tracker의 6D pose를 OpenVR API로 획득, ROS 2 노드에서 publish
- **Ubuntu**: DDS를 통해 동일 네트워크에서 ROS 2 topic을 subscribe하여 시각화

## Prerequisites

### Windows

| 소프트웨어 | 역할 |
|---|---|
| [SteamVR](https://store.steampowered.com/app/250820/SteamVR/) | 트래커 6D pose 데이터 제공 |
| [ViveHub](https://www.vive.com/kr/setup/tracker-ultimate/) | 트래커 드라이버, 맵 생성/관리 (Windows 전용) |
| [pixi](https://pixi.sh/) | 패키지 매니저 (ROS 2 Humble 환경 구성) |

### Ubuntu

| 소프트웨어 | 역할 |
|---|---|
| [pixi](https://pixi.sh/) | 패키지 매니저 (ROS 2 Humble 환경 구성) |

## Setup

### 1. pixi 환경 설치 (Windows & Ubuntu 공통)

```bash
pixi install
```

### 2. CycloneDDS 설정 (Windows)

Windows와 Ubuntu 간 DDS 통신을 위해 CycloneDDS unicast 설정이 필요하다. Multicast가 차단된 네트워크 환경에서 peer IP를 직접 지정하는 방식이다.

`cyclonedds.xml`을 Windows PC에 복사하고, IP 주소를 환경에 맞게 수정한다:

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
                <Peer address="<Ubuntu PC IP>"/>
            </Peers>
            <ParticipantIndex>auto</ParticipantIndex>
        </Discovery>
    </Domain>
</CycloneDDS>
```

`pixi.toml`의 `[feature.win.activation]`에서 `CYCLONEDDS_URI` 경로를 실제 파일 위치로 맞춘다:

```toml
[feature.win.activation]
env = { RMW_IMPLEMENTATION = "rmw_cyclonedds_cpp", CYCLONEDDS_URI = "C:/path/to/cyclonedds.xml" }
```

### 3. SteamVR Headless 설정 (Windows)

HMD 없이 트래커만 사용하려면 SteamVR null driver를 활성화한다:

```bash
python configure-steamvr-headless.py
```

### 4. ViveHub에서 맵 생성 (Windows)

1. Wireless Dongle과 트래커를 ViveHub에서 페어링
2. ViveHub에서 SLAM 기반 공간 맵 생성
3. SteamVR을 실행하여 트래커가 인식되는지 확인

## Usage

### Windows — 트래커 데이터 publish

```bash
# 트래커 노드 + viser 시각화 동시 실행
pixi run launch-track

# 트래커 노드만 실행
pixi run track
```

### Ubuntu — 데이터 subscribe 및 시각화

```bash
# viser 3D 시각화 (http://localhost:8080)
pixi run visualize
```

Windows에서 `pixi run track`을 실행한 상태에서, Ubuntu에서 `pixi run visualize`를 실행하면 트래커 pose가 실시간으로 시각화된다.

#### topic 확인

```bash
pixi shell -e default
ros2 topic list
ros2 topic echo /vive/tracker_0/pose
```

### Ubuntu — mock 데이터로 테스트

실제 트래커 없이 시각화 파이프라인을 검증할 수 있다:

```bash
# mock publisher + viser 시각화
pixi run launch-mock

# 개별 실행
pixi run mock        # mock publisher만
pixi run visualize   # viser 시각화만
```

### Ubuntu — rosbag 재생

```bash
pixi run visualize                                                    # terminal 1
pixi shell -e default -- ros2 bag play sample-data/3f_hw --loop       # terminal 2
```

## Topic Structure

| Topic | Type | Description |
|---|---|---|
| `/vive/tracker_0/pose` | `geometry_msgs/PoseStamped` | 첫 번째 트래커 6D pose |
| `/vive/tracker_1/pose` | `geometry_msgs/PoseStamped` | 두 번째 트래커 6D pose |
| ... | ... | 트래커 수만큼 자동 생성 |

- 좌표계: OpenVR (+Y up, +X right, -Z forward)
- Quaternion: xyzw (ROS 표준)
- Publish rate: 100 Hz (설정 가능)

## Configuration

`config/tracker_params.yaml`에서 파라미터를 조정할 수 있다:

```yaml
vive_tracker_node:
  ros__parameters:
    publish_rate: 100.0
    frame_id: "openvr"

tracker_visualizer_node:
  ros__parameters:
    num_trackers: 2
    viser_port: 8080
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ROS_DOMAIN_ID` | `25` | ROS 2 domain (Windows/Ubuntu 동일해야 함) |
| `RMW_IMPLEMENTATION` | `rmw_cyclonedds_cpp` (Windows) | DDS 구현체 |
| `CYCLONEDDS_URI` | — | CycloneDDS 설정 파일 경로 (Windows) |

## Network Troubleshooting

Windows-Ubuntu 간 topic이 보이지 않을 때:

1. **ROS_DOMAIN_ID 확인**: 양쪽 PC에서 동일한 값인지 확인
2. **CycloneDDS peer IP 확인**: `cyclonedds.xml`의 IP가 올바른지 확인
3. **방화벽 확인**: Windows 방화벽에서 UDP 포트 차단 여부 확인
4. **네트워크 확인**: 두 PC가 같은 서브넷에 있는지 확인
5. **ping 테스트**: 양쪽 PC 간 ping이 되는지 확인
