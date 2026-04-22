# Vive Ultimate Tracker 도입 타당성 평가

Vive Tracker 3.0 (Lighthouse) 환경에서 Vive Ultimate Tracker (Inside-Out) 신규 도입 시 평가 기준 및 절차.

## 1. 트래킹 방식 비교

| 항목 | Tracker 3.0 (Lighthouse) | Ultimate Tracker (Inside-Out) |
|---|---|---|
| 트래킹 원리 | 외부 Base Station IR 스윕 | 온보드 카메라 2대 + SLAM |
| Base Station | 필요 (2~4대) | 불필요 |
| 외부 인프라 | 설치/고정 필요 | 동글만 필요 (USB-C, $40) |
| 좌표 기준 | 외부 절대 기준점 | 환경 특징점 기반 상대 위치 |
| 드리프트 | 없음 | IMU 누적 오차 가능 |

## 2. 성능 비교

### 2.1 정밀도 (Precision)

| 조건 | Tracker 3.0 | Ultimate Tracker | 출처 |
|---|---|---|---|
| 정적 | < 0.5mm 표준편차 | 2.59mm ± 0.81mm (최적) | [1][2] |
| 동적 (평균) | ~10.4mm (80rpm) | 4.98mm ± 4mm | [1][2] |
| 동적 (고속) | 속도 ↑ → 정밀도 ↓ | 30cm/s 이상에서 급감 (6.69~7.01mm) | [2] |
| 캘리브레이션 중심 이격 | 영향 적음 | 100mm 이격 시 26mm 오차 | [2] |

### 2.2 레이턴시 및 주파수

| 항목 | Tracker 3.0 | Ultimate Tracker |
|---|---|---|
| 레이턴시 | < 7ms | ~10ms |
| 갱신 주파수 | ~87Hz (공칭 90Hz) | 미공개 (추정 유사) |

### 2.3 환경 민감도

| 조건 | Tracker 3.0 | Ultimate Tracker |
|---|---|---|
| 밝은 조명 | 영향 적음 | 2.57mm ± 1.07mm (양호) |
| 어두운 조명 | 영향 적음 | 10.64mm ± 3.21mm (성능 저하) |
| 빈 벽/단조로운 환경 | 영향 없음 | 시각적 특징점 부족 시 성능 저하 |
| 반사 표면 | Base Station IR 간섭 가능 | 카메라 기반이므로 글레어 영향 |
| 실외 | Base Station 설치 시 가능 | 부적합 (기준점 부족) |
| 차폐 (Occlusion) | Base Station 시야 확보 필요 | 카메라 가림 시 트래킹 손실 |

## 3. 하드웨어 비교

| 항목 | Tracker 3.0 | Ultimate Tracker |
|---|---|---|
| 무게 | 75g | 94g (+25%) |
| 크기 | 70.9 x 79.0 x 44.1mm | ~50% 더 작음 |
| 배터리 | 7.5시간 | 7시간 |
| 동시 사용 수 | SteamVR 제한 16대 | 동글 당 5대 |
| 단가 | ~$130 | ~$200 |

### 3.1 비용 비교 (TCO)

| 시나리오 | Tracker 3.0 | Ultimate Tracker |
|---|---|---|
| 트래커 3대 + 인프라 (신규) | $390 + Base Station $300 = $690 | $600 + 동글 $40 = $640 |
| 트래커 3대 (Base Station 보유) | $390 | $640 |
| 트래커 3대 (다중 장소 운용) | $390 x N장소 + $300 x N장소 | $640 (장소 무관) |

## 4. 소프트웨어 호환성

| 항목 | 평가 |
|---|---|
| OpenVR API | 동일 API로 pose 획득 가능 (`HmdMatrix34_t`) |
| 좌표계 | 동일 (OpenVR: +Y up, +X right, -Z forward) |
| SteamVR 통합 | 둘 다 지원, Ultimate는 ViveHub 추가 필요 |
| 기존 ROS 2 코드 | 코드 변경 최소 (OpenVR API 레벨 호환) |
| Quaternion | 동일 변환 (OpenVR → ROS xyzw) |

## 5. 평가 기준 (Decision Matrix)

| 평가 항목 | 가중치 | 설명 |
|---|---|---|
| 트래킹 정밀도 | 30% | 용도에 요구되는 위치/자세 정밀도 충족 여부 |
| 레이턴시 | 20% | 실시간 제어/피드백에 미치는 영향 |
| 설치 편의성 | 15% | Base Station 설치/이동 부담 vs 즉시 사용 |
| 환경 내성 | 15% | 실제 운용 환경(조명, 공간, 차폐)에서의 안정성 |
| 비용 (TCO) | 10% | 초기 도입 + 운용 + 다중 장소 비용 |
| SW 호환성 | 10% | 기존 파이프라인 재사용 가능 여부 |

> 가중치는 프로젝트 성격에 따라 조정. 예: 텔레오퍼레이션 → 정밀도/레이턴시 가중, 이동식 데모 → 설치 편의성 가중.

## 6. 평가 절차

### Phase 1 — 요구사항 정의 (1주)

- [ ] 용도 명확화 (텔레오퍼레이션, 모션 캡처, VR FBT 등)
- [ ] 성능 요구사항 정의
  - 허용 위치 오차 (mm)
  - 허용 레이턴시 (ms)
  - 필요 갱신 주파수 (Hz)
  - 동시 트래킹 대수
- [ ] 운용 환경 조건 파악 (조명, 공간, 실내/외)
- [ ] 전환 동기 정리 (Base Station 제거? 이동성? 비용?)
- [ ] 기존 Base Station 인프라 현황 확인

### Phase 2 — 벤치마크 테스트 설계 (1주)

- [ ] Ground truth 기준 결정
  - Vicon/OptiTrack 가용 → 절대 기준
  - 미가용 → Tracker 3.0 대비 상대 비교
- [ ] 테스트 시나리오 정의
  - 정적 정밀도: 고정 위치 N분 데이터 수집 → 분산/표준편차
  - 동적 정밀도: 실 사용 패턴 재현 (저속/고속)
  - 레이턴시: 동일 동작 시간 지연 비교
  - 장시간 안정성: 1시간+ 연속 → 드리프트 측정
  - 환경 교란: 조명 변화, 차폐, 사람 이동
- [ ] 데이터 수집 형식 결정 (rosbag2 기록)

### Phase 3 — 실험 및 데이터 수집 (2주)

- [ ] Ultimate Tracker 샘플 확보 (1~3대 + 동글)
- [ ] 동일 ROS 2 파이프라인으로 데이터 수집
  - 기존 `vive_tracker_node` (OpenVR API) 호환성 확인
  - 양쪽 트래커의 PoseStamped를 rosbag으로 동시 기록
- [ ] 정량 분석
  - RMSE, 표준편차, 최대 오차
  - Bland-Altman plot (두 시스템 일치도)
  - 주파수 응답 분석

### Phase 4 — 종합 평가 및 의사결정 (1주)

- [ ] Decision Matrix 채점 (5단계 평가)
- [ ] 시나리오별 권고안 작성
  - 전면 전환 / 부분 도입 / 현 상태 유지
- [ ] 리스크 정리 (환경 민감도, 드리프트, 호환성)
- [ ] 최종 보고서 작성

## 7. 현재 환경 문제: 구역 C(4대 BS)에서 Tracker 위치 점프

### 7.1 현황

한 층에 세 개의 공간이 존재하며, 두 개의 독립 트래킹 구역을 운용 중:

- **구역 A**: Base Station 2대
- **구역 B**: Base Station 없음 (비트래킹 공간)
- **구역 C**: Base Station 4대 — **벽면 근처에서 위치 점프 빈번 발생 (텔레오퍼레이션 위치)**

### 7.2 공간 배치

```
|              통로                    |
|===== 1.7m 파티션 ====================|
| A (BS 2대) | B |  암막커튼  | C (BS 4대) |
|            |   | (천장까지) |        ★←벽|
|  1.7m 파티션 사이 |         | 점프 발생  |
|================== 벽 ================|

★ = 텔레오퍼레이션 위치 (벽면 근처)
```

구역 간 차단 구조:
- A↔B, B↔C 사이: 1.7m 높이 파티션
- B↔C 사이: 암막커튼 (천장까지 닫힘, 850nm IR 차단 가능)
- 통로↔각 구역: 1.7m 높이 파티션
- BS 설치 높이: 일반적으로 2m+ (파티션보다 높음)

### 7.3 원인 분석

#### 원인 1: 벽면 IR 반사 (Wall IR Reflection) — 가능성 매우 높음

점프 발생 위치가 **벽면 근처(구역 A 반대편)**라는 점이 핵심 단서.
인접 구역 간섭이라면 A 쪽(파티션/커튼 쪽)에서 발생해야 하나, 실제로는 벽 쪽에서 발생.

```
BS ──────→ [벽면] ──반사──→ ★Tracker (벽 근처)
     직접 신호         반사 신호

Tracker가 직접 신호 + 반사 신호를 동시 수신
→ 유령 BS 인식 → 위치 점프
```

벽 근처에서 특히 심한 이유:
- 반사 신호의 경로가 짧아 **신호 강도가 높음**
- 트래커가 **직접 신호와 반사 신호를 거의 동시에** 수신
- BS 4대 → 벽면으로의 스윕 경로 4개 → 반사 신호도 4배

4대 구역이 2대 구역보다 심한 이유:
- 벽을 향해 스윕하는 BS 수가 2배 → 반사 경로도 2배
- 다방향에서 벽면을 스윕하므로 반사 각도가 다양해져 유령 신호 증가

#### 원인 2: 인접 구역 간 IR 간섭 — 가능성 낮음

다음 이유로 가능성이 낮아짐:
- 암막커튼이 천장까지 닫혀 B↔C 직접 경로 차단
- 통로 쪽 1.7m 파티션 위로 우회 가능하나, BS는 하향 각도로 스윕하여 벽면까지 도달하기 어려움
- 점프가 벽면 쪽(A 반대편)에서 발생 → 간섭이 원인이면 A 쪽에서 발생해야 함

#### 원인 3: Base Station 4대 기하학적 경합 — 가능성 보통

4대 BS 중앙이 아닌 벽면 근처에서 발생하므로, 단독 원인보다는 반사와 복합 작용 가능.

#### 원인 4: 무선 동글 RF 간섭 — 가능성 보통

여러 트래커의 2.4GHz 동글이 USB 3.0 포트 근처에 밀집 시 RF 간섭 발생 가능.
USB 3.0은 2.5GHz 대역을 방사하여 동글의 2.4GHz와 간섭.

### 7.4 진단 절차

벽면 반사가 가장 유력하므로 이를 우선 확인:

```
Step 1: 벽면 반사 확인 (최우선)
  └─ 텔레오퍼레이션 위치(★)에서 트래커를 들고
     벽면 쪽을 손/판자로 차폐
      ├─ 점프 감소 → 벽면 반사 확정 → Step 1a
      └─ 변화 없음 → Step 2

  Step 1a: 벽면 재질 확인
    └─ 페인트 (반광/유광)? 타일? 유리? 금속?
       → IR 반사율이 높은 재질 특정

Step 2: BS 배치 확인
  └─ 벽면을 향해 직접 스윕하는 BS가 있는지 확인
      ├─ 있음 → 해당 BS 각도 조정 or 벽 반대쪽으로 재배치
      └─ 없음 → Step 3

Step 3: BS 수량 테스트
  └─ 벽면 쪽 BS 1대씩 끄며 테스트 (4→3→2)
      ├─ 3대에서 안정 → 해당 BS 제거 or 재배치
      └─ 2대에서도 불안정 → Step 4

Step 4: 구역 격리 테스트 (간섭 가능성 배제)
  └─ 구역 A BS 전원 OFF → C만 테스트
      ├─ 여전히 점프 → 벽면 반사 확정 (A 무관)
      └─ 점프 감소 → 간섭도 복합 원인

Step 5: 동글/RF 점검
  └─ 동글 분산 배치, USB 2.0 포트 사용
```

### 7.5 해결 방안

| 방안 | 설명 | 비용 | 기대 효과 |
|---|---|---|---|
| **벽면에 IR 흡수재 부착** | 무광 짙은 색 직물, 펠트, 카펫 타일 등을 벽면에 부착 | 낮음 | 높음 |
| **벽 쪽 BS 각도 재조정** | 벽면 직접 스윕을 줄이도록 하향/내향 조정 | 무료 | 중간 |
| **텔레오퍼레이션 위치 이동** | 벽면에서 50cm+ 이격 | 무료 | 높음 |
| **BS 4대 → 3대 축소** | 벽 쪽 BS 1대 제거로 반사 경로 감소 | 무료 | 중간 |
| **채널 재설정** | 6대 모두 고유 채널 확인 | 무료 | 낮음 (간섭이 주원인 아닐 경우) |
| **동글 분산 배치** | RF 간섭 감소 | USB 연장선 | 낮음 |
| **Ultimate Tracker 전환** | BS 문제 근본 제거 | 높음 ($640+) | 높음 |

> 권장 순서: **벽면 차폐 테스트 → 반사면 처리/BS 각도 조정 → 위치 이동 → BS 축소 → Ultimate 검토**

즉시 확인 가능한 테스트: 텔레오퍼레이션 위치에서 벽면 방향을 판자/골판지로 차폐한 상태로 트래킹 테스트.
점프가 사라지면 벽면 반사가 확정되며, IR 흡수재 부착으로 해결 가능.

### 7.6 Ultimate Tracker 전환 판단 기준

| 조건 | 판단 |
|---|---|
| 벽면 반사 처리로 해결됨 | Tracker 3.0 유지 (정밀도 우위) |
| 벽면 처리 불가 (건물 구조적 제약) | Ultimate 전환 검토 |
| 다중 구역 확장 계획 있음 | Ultimate 전환이 장기적으로 유리 |
| 5mm 이내 정밀도로 충분 | Ultimate 전환 가능 |
| sub-mm 정밀도 필요 | Tracker 3.0 유지, 반사 문제 해결에 투자 |

## 8. Ultimate Tracker 맵 생성 공간 요구사항

### 8.1 최소 공간 크기

| 항목 | 사양 | 출처 |
|---|---|---|
| 최소 플레이 영역 | **3m x 3m** (9m²) | [VIVE 공식 제품 페이지][4] |
| 장애물 이격 거리 | 1.5m 이상 | [VIVE 트래킹 설정 가이드][13] |
| 실제 필요 방 크기 | 약 **6m x 6m** (이격 포함) | — |

```
|←──────── 6m (권장 방 크기) ─────────→|
|  1.5m  |←── 3m (플레이 영역) ──→| 1.5m |
| 이격   |                        | 이격  |
```

대규모 공간은 섹션 분할 스캔:
- 20m² 미만: 섹션 분할 없이 연속 스캔 가능
- 500m²: 약 4m x 4m 단위 섹션
- 1000m²: 약 6m x 6m 단위 섹션

### 8.2 맵 내 사용 위치와 정밀도

**캘리브레이션 중심(맵 중앙)으로부터의 거리에 따라 정밀도가 급격히 저하:**

| 중심 이격 거리 | 위치 오차 | 출처 |
|---|---|---|
| 0 (중심) | 2.59mm ± 0.81mm | [2] |
| 100mm (10cm) | **26mm ± 3.48mm** | [2] |
| 2.1m (3x3 모퉁이) | 데이터 없음, 급격 증가 예상 | — |

3m x 3m 맵의 모퉁이에서 사용 시, 중심으로부터 약 2.1m 이격:

```
  3m
 ┌──────────────┐
 │              │
 │    중심 ●    │ 3m     중심 → 모퉁이 = √(1.5²+1.5²) ≈ 2.1m
 │         \    │
 │          \   │
 └───────────★──┘
           모퉁이
```

10cm 이격에서 이미 26mm 오차가 발생하므로, 모퉁이에서는 **텔레오퍼레이션에 사용하기 어려운 수준의 오차가 예상됨.**

### 8.3 벽 근처 텔레오퍼레이션 시 구조적 한계

현재 구역 C의 텔레오퍼레이션 위치는 벽면 근처이며, 이 경우 Ultimate Tracker는 구조적으로 불리:

```
          1.5m     ★      1.5m
    벽 |◀───────▶|◀──────────▶| 이격 필요
       ↑          ↑
  벽 뒤로는       최소 1.5m 이격 확보 불가
  이격 불가
```

| 문제 | 내용 |
|---|---|
| **맵 생성 공간 부족** | 벽 뒤로 1.5m 이격 불가 → 최소 공간 요건 미충족 |
| **맵 중심 배치 불가** | 중심을 벽 근처에 두면 한쪽 스캔 범위가 벽으로 잘림 → 맵 품질 저하 |
| **정밀도 저하** | 맵 중심을 벽에서 떨어뜨리면 사용 위치가 중심에서 이격 → 오차 급증 |
| **SLAM 특징점 부족** | 벽 방향은 근거리 단색면 → 카메라 시야의 특징점 부족 |

### 8.4 결론: 벽 근처 고정 위치 텔레오퍼레이션에는 Ultimate Tracker 부적합

**벽 근처 고정 위치 텔레오퍼레이션 용도에서는 Ultimate Tracker가 구조적으로 불리하며,
Base Station 기반 Tracker 3.0이 적합.** 구역 C의 벽면 위치 점프 문제는
IR 반사 처리(흡수재 부착, BS 각도 조정)로 해결하는 것이 현실적.

| 접근 | 권고 |
|---|---|
| **현재 문제 해결** | Tracker 3.0 유지 + 벽면 IR 반사 처리 (섹션 7.5 참조) |
| **Ultimate Tracker 전환** | 벽 근처 텔레오퍼레이션 용도에서는 비권고 |

> "공간이 충분한가"보다 **"사용 위치가 맵 중심에 있는가"**가 핵심이며,
> 벽 근처 사용은 이 조건을 구조적으로 충족하기 어려움.

## 9. 운용 안정성 비교 (Operational Stability)

Tracker 3.0은 "설치 후 잊어버려도 되는(set-and-forget)" 시스템이고,
Ultimate Tracker는 "환경을 지속적으로 관리해야 하는" 시스템이다.

### 9.1 운용 모델 비교

| 관점 | Tracker 3.0 (Lighthouse) | Ultimate Tracker (Inside-Out) |
|---|---|---|
| **초기 설정** | BS 설치 후 완료 (1회성) | 맵 스캔 필요 (공간별, 조건별) |
| **환경 변화 대응** | 영향 없음 (외부 절대 기준) | 맵 재생성 필요 (가구 이동, 조명 변화 등) |
| **환경 의존성** | 없음 | 조명, 시각적 특징점, 공간 크기에 의존 |
| **트래킹 보장성** | 설치 후 일관된 성능 | 환경 변화 시 성능 보장 불가 |
| **추가 인프라** | BS (이미 보유) | ViveHub + Windows PC 추가 필요 |

### 9.2 운용 오버헤드 상세

#### 맵 생성 부담

- 공간별로 개별 맵 스캔 필요 (무릎 높이 + 서서 + 4방향 회전)
- 최소 3m x 3m + 1.5m 이격 공간 요구
- 맵 품질이 트래킹 성능에 직결 → 스캔 품질 관리 필요

#### 환경 변화에 대한 취약성

SLAM 기반 트래킹은 맵 생성 시점의 환경 특징점에 의존.
이후 환경이 변하면 트래킹 성능 저하 또는 맵 재생성이 필요:

| 환경 변화 | 영향 |
|---|---|
| 가구/장비 이동 | 특징점 변화 → 트래킹 불안정 가능 |
| 조명 조건 변화 (시간대, 계절) | 카메라 인식 품질 변화 → 정밀도 저하 |
| 벽면 포스터/게시물 변경 | 시각적 특징점 소실 → 맵 불일치 |
| 사람/물체 이동 (동적 환경) | 일시적 특징점 교란 |

> Tracker 3.0은 IR 기반 절대 좌표 시스템이므로 위 변화에 영향 없음.

#### 추가 Windows PC 필요

- Ultimate Tracker는 ViveHub 소프트웨어를 통해 맵 생성 및 관리
- ViveHub는 Windows 전용 → 기존 인프라에 Windows PC가 없으면 추가 도입 필요
- Tracker 3.0은 SteamVR만으로 운용 가능 (이미 구축됨)

### 9.3 운용 리스크 요약

| 리스크 | 발생 조건 | 영향 | Tracker 3.0 해당 여부 |
|---|---|---|---|
| 맵 재생성 필요 | 환경 변화 발생 시 | 운용 중단 + 재스캔 시간 | 해당 없음 |
| 트래킹 성능 예측 불가 | 환경이 맵과 불일치 시 | 정밀도 불명, 갑작스런 저하 가능 | 해당 없음 |
| 추가 인프라 비용 | Windows PC 미보유 시 | HW + SW 추가 비용 | 해당 없음 |
| 맵 스캔 품질 관리 | 상시 | 담당자 교육, 절차 수립 필요 | 해당 없음 |

## 10. 시나리오별 예상 판정

| 시나리오 | 예상 권고 | 근거 |
|---|---|---|
| 고정 장소, 고정밀 필요 | Tracker 3.0 유지 | sub-mm 정밀도, 드리프트 없음 |
| 다중 장소 이동, 5mm 허용 | Ultimate 전환 | Base Station 불필요, TCO 유리 |
| 고정 장소, Base Station 설치 불가 | Ultimate 도입 | 물리적 제약 해소 |
| 혼합 사용 (정밀 + 이동) | 병행 운용 | 장소별 최적 선택 |
| 다중 구역 BS 간섭 해결 불가 | Ultimate 전환 | BS 인프라 문제 근본 제거 |
| 다중 구역 BS 간섭, 채널/차단으로 해결 | Tracker 3.0 유지 | 정밀도 우위, 추가 비용 없음 |

## References

- [1] [Tracker 3.0 vs Vicon Accuracy (Sensors 2023)](https://www.mdpi.com/1424-8220/23/17/7371)
- [2] [Ultimate Tracker Precision Evaluation (arxiv 2024)](https://arxiv.org/html/2409.01947v2)
- [3] [VIVE Tracker Accessory Comparison](https://www.vive.com/us/accessory-comparison/)
- [4] [Ultimate Tracker Official Page](https://www.vive.com/us/accessory/vive-ultimate-tracker/)
- [5] [Ultimate Tracker Troubleshooting](https://www.vive.com/us/support/ultimate-tracker/category_howto/tracking-is-not-stable-or-accurate.html)
- [6] [Tracker 3.0 vs Ultimate Tracker Comparison](https://gadgetslogs.com/reviews/vive-tracker-3-0-vs-vive-ultimate-tracker/)
- [7] [VIVE Robotics](https://www.viverobotics.ai/)
- [8] [Steam Support: Base Station & Lighthouse Tracking](https://help.steampowered.com/en/faqs/view/1AF1-670B-FF5C-3323)
- [9] [Base Station 2.0 Channel Configuration](https://steamcommunity.com/app/358720/discussions/0/1694920442950668056/)
- [10] [HTC 16 Base Station Multi-Room Experiment](https://www.roadtovr.com/htc-experiments-with-16-base-stations-steamvr-tracking-2-0-multi-room/)
- [11] [Vive Tracker Placement & Interference Guide](https://www.nerdaxic.com/2023/06/17/best-practices-for-htc-vive-tracker-placement-to-reduce-interference/)
- [12] [Adjacent Room Base Station Conflict](https://forum.htc.com/topic/1144-2-vive-systems-in-same-big-room-creates-base-station-conflict/)
- [13] [Setting up play area for tracking](https://business.vive.com/us/support/vive-lbss/category_howto/setting-up-your-play-area-for-tracking.html)
- [14] [Setting up play area for map creation](https://business.vive.com/us/support/vive-lbss/category_howto/setting-up-the-play-area-for-map-creation.html)
