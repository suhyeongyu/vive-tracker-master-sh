import openvr
import time
import math
import os

def matrix_to_euler(matrix):
    """3x4 행렬에서 Euler Angles (Roll, Pitch, Yaw) 추출"""
    sy = math.sqrt(matrix[0][0] * matrix[0][0] + matrix[1][0] * matrix[1][0])
    singular = sy < 1e-6
    if not singular:
        x, y, z = math.atan2(matrix[2][1], matrix[2][2]), math.atan2(-matrix[2][0], sy), math.atan2(matrix[1][0], matrix[0][0])
    else:
        x, y, z = math.atan2(-matrix[1][2], matrix[1][1]), math.atan2(-matrix[2][0], sy), 0
    return math.degrees(x), math.degrees(y), math.degrees(z)

def track_multiple_trackers():
    try:
        vr_system = openvr.init(openvr.VRApplication_Other)
    except openvr.OpenVRError as e:
        print(f"초기화 실패: {e}")
        return

    print("트래커 탐색 중...")
    
    try:
        while True:
            # 포즈 데이터 업데이트
            poses = vr_system.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)
            
            output = []
            output.append(f"{'ID':<4} | {'Serial':<15} | {'X':>6} {'Y':>6} {'Z':>6} | {'Roll':>6} {'Pitch':>6} {'Yaw':>6}")
            output.append("-" * 85)

            tracker_count = 0
            for i in range(openvr.k_unMaxTrackedDeviceCount):
                if vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_GenericTracker:
                    pose = poses[i]
                    serial = vr_system.getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String)
                    
                    if pose.bPoseIsValid:
                        m = pose.mDeviceToAbsoluteTracking
                        x, y, z = m[0][3], m[1][3], m[2][3]
                        r, p, y_deg = matrix_to_euler(m)
                        
                        line = f"[{i:02d}] | {serial:<15} | {x:6.2f} {y:6.2f} {z:6.2f} | {r:6.1f} {p:6.1f} {y_deg:6.1f}"
                    else:
                        line = f"[{i:02d}] | {serial:<15} | [ 추적 불가 (Out of View) ]"
                    
                    output.append(line)
                    tracker_count += 1

            # 화면 갱신 (터미널 청소)
            os.system('cls' if os.name == 'nt' else 'clear')
            print("\n".join(output))
            
            if tracker_count == 0:
                print("연결된 트래커를 찾을 수 없습니다. SteamVR 상태를 확인하세요.")

            time.sleep(0.02) # 약 50Hz 갱신

    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        openvr.shutdown()

if __name__ == "__main__":
    track_multiple_trackers()