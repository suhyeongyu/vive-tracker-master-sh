# Vive Tracker Test

## Device

- HTC Vive Ultimate Tracker

## Architecture

```
[Windows: SteamVR + ViveHub + ROS 2 Node] -- DDS --> [Linux: ROS 2 Node]
```

- **Windows**: SteamVR 및 ViveHub를 통해 Vive Ultimate Tracker의 6D pose 데이터를 OpenVR API로 획득, ROS 2 노드에서 직접 publish
- **Linux**: DDS를 통해 동일 네트워크에서 ROS 2 topic을 직접 subscribe

## Environment

- pixi + robostack-humble
- ROS 2 Humble

## Usage

### Linux (verification with mock data)

```bash
pixi run launch-mock        # mock publisher + viser visualizer
pixi run mock               # mock publisher only
pixi run visualize          # viser visualizer only (http://localhost:8080)
```

### Linux (rosbag replay)

```bash
pixi run visualize                              # terminal 1: viser visualizer
pixi shell -e default -- ros2 bag play sample-data/3f_hw --loop  # terminal 2: bag replay
```

### Windows (real tracker)

```bash
pixi run launch-track       # tracker + viser visualizer
pixi run track              # tracker only
```

## Topic Structure

- `/vive/tracker_0/pose` — `geometry_msgs/PoseStamped` (OpenVR coords, quat xyzw)
- `/vive/tracker_1/pose` — ...
