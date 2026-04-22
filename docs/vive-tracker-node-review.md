# vive_tracker_node.py 코드 리뷰

> 대상: `src/vive_tracker/vive_tracker_node.py`
> 날짜: 2026-03-02

## 1. Publish Rate 정확도

### 현재 방식: Timer 기반 폴링

```python
self.timer = self.create_timer(1.0 / rate, self.timer_callback)
```

ROS 2 `create_timer`는 soft timer로 정확한 주기를 보장하지 않는다.

- 콜백 실행 시간이 period에 포함되지 않아 실제 rate가 `1/(period + callback_duration)`으로 저하
- ROS 2 executor는 single-threaded — 콜백 실행 중 다음 timer가 밀림
- 100Hz (10ms period)에서 콜백이 2-3ms 걸리면 실제 rate는 ~80-90Hz

### 근본적 문제: OpenVR 업데이트 주기와 비동기

Vive Ultimate Tracker는 100Hz로 데이터를 생성하지만, timer 폴링은 OpenVR의 실제 업데이트 주기와 phase가 맞지 않는다.
같은 pose를 두 번 읽거나, 한 프레임을 건너뛸 수 있다.

### 권장: WaitGetPoses 동기화

`WaitGetPoses()`는 SteamVR의 vsync에 동기화되어 정확히 프레임당 1회 호출된다.
Blocking이므로 별도 스레드에서 실행 필요.

```python
# 개념적 구조
def _tracking_thread(self):
    while rclpy.ok():
        poses = openvr.VRCompositor().waitGetPoses([], [])
        self._publish_poses(poses)
```

## 2. 콜백 내 불필요한 연산

### 행렬 복사: Python 이중 루프

```python
m = np.eye(4)                  # 매번 힙 할당
for row in range(3):           # 12회 Python-level 루프
    for col in range(4):
        m[row, col] = pose.mDeviceToAbsoluteTracking[row][col]
```

개선: `np.ctypeslib.as_array`로 한 줄 복사, 또는 pre-allocated buffer 재사용.

```python
m = np.ctypeslib.as_array(
    pose.mDeviceToAbsoluteTracking, shape=(3, 4)
)
```

### 쿼터니언 변환: scipy 과다

```python
quat_xyzw = Rotation.from_matrix(m[:3, :3]).as_quat()
```

회전행렬 → 쿼터니언 변환에 scipy는 과하다. 직접 구현하면 import 제거 + 속도 향상.

```python
def _mat_to_quat(R):
    """3x3 rotation matrix -> (x, y, z, w) quaternion."""
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = 0.5 / np.sqrt(t + 1.0)
        return (
            (R[2, 1] - R[1, 2]) * s,
            (R[0, 2] - R[2, 0]) * s,
            (R[1, 0] - R[0, 1]) * s,
            0.25 / s,
        )
    # ... (다른 분기)
```

## 3. 디바이스 전수 순회

```python
for i in range(openvr.k_unMaxTrackedDeviceCount):  # 64회 반복
    if self.vr_system.getTrackedDeviceClass(i) != ...:
        continue
```

매 콜백마다 64개 디바이스를 순회하며 `getTrackedDeviceClass()`를 호출한다.
트래커 인덱스는 거의 바뀌지 않으므로, 발견된 인덱스를 캐싱하고 주기적으로만 re-scan하면 된다.

## 4. QoS 설정

```python
pub = self.create_publisher(PoseStamped, topic, 10)
```

100Hz에서 depth 10은 subscriber가 ~100ms 지연되면 데이터 유실.
센서 데이터에는 `BEST_EFFORT` + `KEEP_LAST(1)`이 일반적:

```python
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

sensor_qos = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)
pub = self.create_publisher(PoseStamped, topic, sensor_qos)
```

## 5. 기타

- **예측 시간 `0`** (L62): `getDeviceToAbsoluteTrackingPose`의 두 번째 인자가 0이면 예측 없이 마지막 측정값 반환. publish까지의 latency를 보상하려면 예측 시간을 넣을 수 있으나, 실측 기반이라면 0이 적절.
- **Type hint**: `dict[int, tuple]` → `dict[int, tuple[Publisher, str]]`로 명시하면 가독성 향상.

## 요약

| 항목 | 현재 | 권장 | 영향도 |
|------|------|------|--------|
| 타이밍 | Timer 폴링 (rate 부정확) | `WaitGetPoses()` + 별도 스레드 | 높음 |
| 행렬 복사 | Python 이중 루프 | `np.ctypeslib.as_array` / pre-alloc | 중간 |
| 쿼터니언 | scipy Rotation | 직접 구현 | 중간 |
| 디바이스 탐색 | 매 콜백 64회 순회 | 캐싱 + 주기적 re-scan | 낮음 |
| QoS | depth=10, RELIABLE | `BEST_EFFORT`, `KEEP_LAST(1)` | 낮음 |
