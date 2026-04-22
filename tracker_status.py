import openvr
import sys

def get_tracker_status():
    try:
        # OpenVR 초기화 (VRApplication_Other: 헤드셋 없이도 실행 가능하게 설정)
        vr_system = openvr.init(openvr.VRApplication_Other)
    except openvr.OpenVRError as e:
        print(f"OpenVR 초기화 실패: {e}")
        return

    print(f"{'Index':<6} {'Serial Number':<15} {'Status':<12} {'Battery':<8}")
    print("-" * 50)

    # OpenVR의 최대 장치 개수만큼 루프 (보통 64개)
    for i in range(openvr.k_unMaxTrackedDeviceCount):
        device_class = vr_system.getTrackedDeviceClass(i)
        
        # 장치 클래스가 GenericTracker(트래커)인 경우만 처리
        if device_class == openvr.TrackedDeviceClass_GenericTracker:
            
            # 1. 연결 상태 확인
            is_connected = vr_system.isTrackedDeviceConnected(i)
            status = "Connected" if is_connected else "Disconnected"

            # 2. 시리얼 번호 가져오기
            serial = vr_system.getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String)

            # 3. 배터리 정보 가져오기 (0.0 ~ 1.0 사이의 값 반환)
            battery_pct = vr_system.getFloatTrackedDeviceProperty(i, openvr.Prop_DeviceBatteryPercentage_Float)
            battery_str = f"{int(battery_pct * 100)}%" if is_connected else "N/A"

            # 4. (참고) 모델 이름
            model_name = vr_system.getStringTrackedDeviceProperty(i, openvr.Prop_ModelNumber_String)

            print(f"{i:<6} {serial:<15} {status:<12} {battery_str:<8} ({model_name})")

    # 종료
    openvr.shutdown()

if __name__ == "__main__":
    get_tracker_status()