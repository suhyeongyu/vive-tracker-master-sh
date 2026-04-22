import time
import openvr
import viser
import numpy as np
from scipy.spatial.transform import Rotation as R
from collections import deque

def get_pose_matrix(openvr_matrix):
    m = np.eye(4)
    for i in range(3):
        for j in range(4):
            m[i, j] = openvr_matrix[i][j]
    return m

def main():
    try:
        vr_system = openvr.init(openvr.VRApplication_Other)
    except openvr.OpenVRError as e:
        print(f"OpenVR 초기화 실패: {e}")
        return

server = viser.ViserServer(host="0.0.0.0", port=8080)
    tracker_info = {}
    
    # 루프 속도 측정을 위한 변수
    frame_count = 0
    start_time = time.perf_counter()

    try:
        while True:
            # 1. 원자적 업데이트 시작 (이 안의 모든 변경사항은 한 패킷으로 묶임)
            with server.atomic():
                poses = vr_system.getDeviceToAbsoluteTrackingPose(
                    openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount
                )
                current_time = time.perf_counter()

                for i in range(openvr.k_unMaxTrackedDeviceCount):
                    if vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_GenericTracker:
                        pose = poses[i]
                        if pose.bPoseIsValid:
                            if i not in tracker_info:
                                # 초기화 로직 (동일)
                                serial = vr_system.getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String)
                                path = f"/trackers/tracker_{i}"
                                tracker_info[i] = {
                                    "frame": server.scene.add_frame(path, show_axes=True, axes_length=0.1),
                                    "label": server.scene.add_label(f"{path}/label", text=""),
                                    "gui": None, # 나중에 생성
                                    "last_time": current_time,
                                    "timestamps": deque(maxlen=30)
                                }
                                with server.gui.add_folder(f"Tracker {i}"):
                                    tracker_info[i]["gui"] = server.gui.add_text("Hz", initial_value="...")

                            info = tracker_info[i]
                            dt = current_time - info["last_time"]
                            if dt > 0: info["timestamps"].append(dt)
                            info["last_time"] = current_time
                            
                            avg_dt = np.mean(info["timestamps"]) if info["timestamps"] else 0
                            hz = 1.0 / avg_dt if avg_dt > 0 else 0

                            # [핵심] 위치/회전 업데이트 (매우 가벼움)
                            mat = get_pose_matrix(pose.mDeviceToAbsoluteTracking)
                            info["frame"].position = mat[:3, 3]
                            info["frame"].wxyz = R.from_matrix(mat[:3, :3]).as_quat()[[3, 0, 1, 2]]

                            # [핵심] 텍스트 업데이트 제한 (약 0.5초마다 한 번씩만)
                            if frame_count % 50 == 0:
                                info["label"].text = f"ID {i} | {hz:.1f} Hz"
                                info["gui"].value = f"{hz:.1f} Hz"

            # 2. 전송 주기 제어 (100Hz로 제한)
            # 너무 빠르면 WebSocket 버퍼가 가득 차서 지연(Latency)이 발생함
            frame_count += 1
            time.sleep(0.020) 

            # 1초마다 실제 루프 속도 출력 (디버깅용)
            if frame_count % 100 == 0:
                elapsed = time.perf_counter() - start_time
                # print(f"실제 전송 속도: {100/elapsed:.1f} FPS")
                start_time = time.perf_counter()

    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        openvr.shutdown()

if __name__ == "__main__":
    main()