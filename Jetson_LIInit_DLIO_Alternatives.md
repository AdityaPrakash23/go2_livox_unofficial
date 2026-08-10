# Jetson alternatives for Go2 odometry instability

This is the short runbook for two backup paths when FAST-LIO odometry is unstable on the Go2:

1. Run LI-Init inside Docker on the Jetson to calibrate Livox MID-360 LiDAR-IMU extrinsics.
2. Test DLIO as a replacement odometry source for Nav2.

Use these only after confirming the simple operational fallback still works:

```bash
ros2 launch go2_robot_sdk navigation.launch.py \
  map:=/home/orin/test_sdk_ws/testLab.yaml \
  use_fast_lio_odom:=false \
  driver_odom_tf:=true \
  driver_odom_topic:=true \
  use_livox_custom_to_pointcloud2:=false \
  navigation_cloud_topic:=/livox/lidar \
  foxglove:=false \
  enable_video:=false
```

## Before either alternative

Always verify there is only one odometry source:

```bash
ros2 topic info /odom -v
ros2 run tf2_ros tf2_echo odom base_link
```

For Nav2, the final TF chain must be:

```text
map -> odom -> base_link -> livox_frame
```

Do not allow Go2 odometry and FAST-LIO/DLIO to both publish `/odom` or `odom -> base_link`.

## Alternative A: LI-Init calibration on Jetson with Docker

Use this when FAST-LIO standalone odometry drifts while stationary or creates fake x/y/z translation during pure rotation.

### A1. Install Docker on the Jetson

```bash
sudo apt update
sudo apt install -y docker.io
sudo usermod -aG docker $USER
newgrp docker
```

Create persistent folders:

```bash
mkdir -p ~/li_init_docker_ws/bags
mkdir -p ~/li_init_docker_ws/results
```

### A2. Build a ROS1 Noetic Docker image

Create `~/li_init_docker_ws/Dockerfile` using the longer guide in:

```text
go2_livox_unofficial/LI_Init_Docker_Setup.md
```

Then build:

```bash
cd ~/li_init_docker_ws
docker build -t li-init-noetic-mid360:go2 .
```

### A3. Start the container

Stop all host ROS2 Livox drivers first.

```bash
docker run -it --rm \
  --name li_init_noetic \
  --network host \
  --ipc host \
  --privileged \
  -v ~/li_init_docker_ws:/root/li_init_docker_ws \
  li-init-noetic-mid360:go2 \
  bash
```

Inside the container:

```bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
```

### A4. Run ROS1 Livox driver

Inside container terminal 1:

```bash
roslaunch livox_ros_driver2 msg_MID360.launch
```

If that launch name differs:

```bash
ls /root/catkin_ws/src/livox_ros_driver2/launch_ROS1
```

Verify:

```bash
rostopic hz /livox/lidar
rostopic hz /livox/imu
```

Expected:

```text
/livox/lidar: about 10 Hz
/livox/imu: about 200 Hz
```

### A5. Run LI-Init

Inside container terminal 2:

```bash
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
roslaunch lidar_imu_init mid360_go2.launch
```

If `mid360_go2.launch` does not exist yet, create it from the LI-Init Livox example as described in `LI_Init_Docker_Setup.md`.

Calibration movement:

1. Keep robot completely still for 5 to 10 seconds after startup.
2. Slowly yaw left/right.
3. Add gentle pitch/roll motion only if safe.
4. Add slow translation in a feature-rich area.
5. Continue 60 to 120 seconds.
6. Avoid empty rooms, glass, mostly-floor views, and violent shaking.

### A6. Save result

Inside the container:

```bash
cp /root/catkin_ws/src/LiDAR_IMU_Init/result/Initialization_result.txt \
   /root/li_init_docker_ws/results/Initialization_result_mid360_go2.txt
```

On the Jetson host, read:

```bash
cat ~/li_init_docker_ws/results/Initialization_result_mid360_go2.txt
```

Copy the LI-Init result into ROS2 FAST-LIO config:

```text
~/livox-ws/src/FAST_LIO/config/mid360_go2_nav.yaml
```

Fields to update:

```yaml
common:
  time_offset_lidar_to_imu: RESULT_TIME_OFFSET

mapping:
  extrinsic_est_en: false
  extrinsic_T: [ RESULT_TX, RESULT_TY, RESULT_TZ ]
  extrinsic_R: [ R00, R01, R02,
                 R10, R11, R12,
                 R20, R21, R22 ]
```

Rebuild FAST-LIO:

```bash
cd ~/livox-ws
colcon build --packages-select fast_lio
source install/setup.bash
```

### A7. Validate FAST-LIO before Nav2

```bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
ros2 launch fast_lio mapping.launch.py
ros2 topic echo /Odometry --field pose.pose.position
```

Pass criteria:

- Stationary for 60 seconds: x/y/z move only a few cm.
- Pure rotation: yaw changes, x/y/z do not walk away.
- No repeated `No Effective Points!` during slow movement in a feature-rich area.

Only then reconnect FAST-LIO to Nav2.

## Alternative B: DLIO instead of FAST-LIO

Use this if FAST-LIO remains unstable after checking transforms/timestamps/calibration.

DLIO local reference path:

```text
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry
```

Go2-specific DLIO files previously added:

```text
direct_lidar_inertial_odometry/cfg/dlio_go2_mid360.yaml
direct_lidar_inertial_odometry/cfg/params_go2_mid360.yaml
direct_lidar_inertial_odometry/launch/dlio_go2_mid360.launch.py
```

### B1. Install dependencies on Jetson

```bash
sudo apt update
sudo apt install -y \
  libomp-dev \
  libpcl-dev \
  libeigen3-dev \
  ros-humble-pcl-ros \
  ros-humble-pcl-conversions \
  ros-humble-tf2-ros
```

### B2. Put DLIO in a ROS2 workspace

Recommended on the Jetson:

```bash
mkdir -p ~/dlio_ws/src
cp -r /home/orin/test_sdk_ws/src/direct_lidar_inertial_odometry ~/dlio_ws/src/
```

If the repo is available through Git, clone it instead:

```bash
cd ~/dlio_ws/src
git clone -b feature/ros2 https://github.com/vectr-ucla/direct_lidar_inertial_odometry.git
```

Then copy the Go2-specific config/launch files into the cloned DLIO package if they are not already there.

### B3. Build DLIO

```bash
cd ~/dlio_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select direct_lidar_inertial_odometry
source install/setup.bash
```

### B4. Run Livox in PointCloud2 mode

For DLIO, start with native PointCloud2, not CustomMsg:

```bash
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Verify:

```bash
ros2 topic info /livox/lidar -v
ros2 topic hz /livox/lidar
ros2 topic hz /livox/imu
```

Expected:

```text
/livox/lidar: sensor_msgs/msg/PointCloud2
/livox/imu: sensor_msgs/msg/Imu
```

### B5. Run DLIO standalone

```bash
source /opt/ros/humble/setup.bash
source ~/dlio_ws/install/setup.bash
ros2 launch direct_lidar_inertial_odometry dlio_go2_mid360.launch.py \
  rviz:=false \
  pointcloud_topic:=/livox/lidar \
  imu_topic:=/livox/imu \
  odom_topic:=/odom
```

Validate:

```bash
ros2 topic info /odom -v
ros2 topic hz /odom
ros2 run tf2_ros tf2_echo odom base_link
ros2 topic echo /odom --field pose.pose.position
```

Pass criteria:

- Stationary for 60 seconds: position stays within a few cm.
- Pure rotation: yaw changes, x/y/z do not drift heavily.
- Slow 0.5 m translation: odom moves in the correct direction and then settles.

Do not start Nav2 until this standalone test passes.

### B6. Optional DLIO odom adapter

A DLIO adapter has been added to this Go2 package:

```text
go2_robot_sdk/go2_robot_sdk/dlio_odom_adapter.py
```

It installs as:

```bash
ros2 run go2_robot_sdk dlio_odom_adapter
```

Default behavior:

```text
input_topic: /dlio/odom_node/odom
output_topic: /odom
publish_tf: false
force_2d: true
```

Use this adapter only if DLIO publishes odometry on `/dlio/odom_node/odom` instead of `/odom`.

Example:

```bash
ros2 run go2_robot_sdk dlio_odom_adapter --ros-args \
  -p input_topic:=/dlio/odom_node/odom \
  -p output_topic:=/odom \
  -p publish_tf:=false \
  -p force_2d:=true \
  -p smoothing_alpha:=0.8 \
  -p max_position_jump:=0.35 \
  -p max_yaw_jump:=0.6
```

Keep `publish_tf:=false` if DLIO itself is already broadcasting `odom -> base_link`. Two TF publishers for the same transform will break localization.

### B7. Run Nav2 with DLIO

Use this only after DLIO standalone odometry is stable.

Terminal 1: Livox PointCloud2.

```bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Terminal 2: DLIO publishing `/odom`.

```bash
source /opt/ros/humble/setup.bash
source ~/dlio_ws/install/setup.bash
ros2 launch direct_lidar_inertial_odometry dlio_go2_mid360.launch.py \
  rviz:=false \
  pointcloud_topic:=/livox/lidar \
  imu_topic:=/livox/imu \
  odom_topic:=/odom
```

Terminal 3: Nav2 with Go2 odom and FAST-LIO disabled.

```bash
source /opt/ros/humble/setup.bash
source ~/test_sdk_ws/install/setup.bash
export ROBOT_IP="192.168.123.161"

ros2 launch go2_robot_sdk navigation.launch.py \
  map:=/home/orin/test_sdk_ws/testLab.yaml \
  use_fast_lio_odom:=false \
  driver_odom_tf:=false \
  driver_odom_topic:=false \
  use_livox_custom_to_pointcloud2:=false \
  navigation_cloud_topic:=/livox/lidar \
  foxglove:=false \
  enable_video:=false
```

Before sending a goal:

```bash
ros2 topic info /odom -v
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo map odom
ros2 topic hz /scan
```

Then send a tiny Nav2 goal first, about 0.3 to 0.5 m forward.

## Decision rule

1. If Go2 odom + AMCL is stable enough, use it for immediate demos.
2. If FAST-LIO fails stationary/pure-rotation tests, do LI-Init calibration.
3. If FAST-LIO is still unstable after calibration, try DLIO standalone.
4. Only connect any odometry source to Nav2 after `odom -> base_link` is stable while stationary.
5. Never debug Nav2 goals while `/odom` itself is jumping.
