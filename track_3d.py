import openvr
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

class VRTrackerVisualizer:
    def __init__(self):
        # OpenVR 초기화
        try:
            self.vr_system = openvr.init(openvr.VRApplication_Other)
        except openvr.OpenVRError as e:
            print(f"OpenVR Error: {e}")
            exit()

        # 그래프 설정
        self.fig = plt.figure(figsize=(10, 8))
        self.ax = self.fig.add_subplot(111, projection='3d')
        
        # 축 범위 설정 (단위: 미터, -2m ~ 2m 범위)
        self.ax.set_xlim([-2, 2])
        self.ax.set_ylim([-2, 2])
        self.ax.set_zlim([0, 2]) # 바닥에서부터 높이 2m
        
        self.ax.set_xlabel('X (Right)')
        self.ax.set_ylabel('Z (Depth)')
        self.ax.set_zlabel('Y (Up)')
        self.ax.set_title('Live Vive Tracker 3D Plot')

        # 트래커별로 다른 색상 지정용
        self.colors = ['red', 'blue', 'green', 'orange', 'purple']
        self.scatters = {} # {device_index: scatter_object}
        self.texts = {}    # {device_index: text_object}

    def update(self, frame):
        # 포즈 데이터 가져오기
        poses = self.vr_system.getDeviceToAbsoluteTrackingPose(
            openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount
        )

        for i in range(openvr.k_unMaxTrackedDeviceCount):
            device_class = self.vr_system.getTrackedDeviceClass(i)
            
            # 트래커인 경우만 처리
            if device_class == openvr.TrackedDeviceClass_GenericTracker:
                pose = poses[i]
                
                if pose.bPoseIsValid:
                    m = pose.mDeviceToAbsoluteTracking
                    # OpenVR 좌표계: X(좌우), Y(상하), Z(앞뒤)
                    # Matplotlib에서 보기 좋게 Z와 Y의 순서를 바꿔서 시각화하기도 합니다.
                    x, y, z = m[0][3], m[1][3], m[2][3]
                    
                    # 해당 인덱스의 점이 없으면 생성, 있으면 위치 업데이트
                    if i not in self.scatters:
                        color = self.colors[len(self.scatters) % len(self.colors)]
                        serial = self.vr_system.getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String)
                        
                        self.scatters[i] = self.ax.scatter([], [], [], c=color, s=100, label=f"ID {i}: {serial[-5:]}")
                        self.texts[i] = self.ax.text(x, z, y, f"ID {i}", size=10, zorder=1, color='black')
                        self.ax.legend()

                    # 위치 업데이트 (Matplotlib 3D scatter는 _offsets3d를 통해 업데이트)
                    self.scatters[i]._offsets3d = (np.array([x]), np.array([z]), np.array([y]))
                    self.texts[i].set_position((x, z))
                    self.texts[i].set_3d_properties(y, 'z')

        return list(self.scatters.values()) + list(self.texts.values())

    def run(self):
        # 약 30 FPS 정도로 업데이트 (interval=33ms)
        ani = FuncAnimation(self.fig, self.update, interval=33, blit=False)
        plt.show()
        openvr.shutdown()

if __name__ == "__main__":
    viz = VRTrackerVisualizer()
    viz.run()