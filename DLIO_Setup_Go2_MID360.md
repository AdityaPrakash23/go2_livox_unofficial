# DLIO setup for Unitree Go2 + Livox MID-360 + Nav2

This guide installs and tests DLIO as a backup odometry source for the Go2 when FAST-LIO is unstable.

DLIO repo:

```
https://github.com/vectr-ucla/direct_lidar_inertial_odometry
```

The local reference copy has been cloned here:

```
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry
```

Branch used:

```
feature/ros2
```

The upstream README says the ROS2 branch supports ROS Humble, `sensor_msgs/msg/PointCloud2` input, and `sensor_msgs/msg/Imu` input. That matches the preferred Livox MID-360 setup for Nav2 because AMCL/Nav2 already need PointCloud2-derived laser data.

## Goal

Replace this unstable chain:

```
FAST-LIO /Odometry -> fast_lio_odom_adapter -> /odom -> odom -> base_link
```

with this DLIO chain:

```
DLIO -> /odom -> odom -> base_link
```

Nav2 still expects:

```
map -> odom -> base_link -> livox_frame
```

AMCL provides `map -> odom`. DLIO provides `odom -> base_link`.

## Files added locally

The DLIO package was cloned as a sibling of `go2_livox_unofficial` and `livox-ws`:

```
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry
```

Go2-specific files added inside DLIO:

```
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry/cfg/dlio_go2_mid360.yaml
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry/cfg/params_go2_mid360.yaml
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry/launch/dlio_go2_mid360.launch.py
```

These files leave the upstream DLIO defaults untouched.

## Important Livox mode

For the first DLIO attempt, use Livox PointCloud2 mode.

Preferred input:

```
/livox/lidar: sensor_msgs/msg/PointCloud2
/livox/imu:   sensor_msgs/msg/Imu
```

Do not start with Livox CustomMsg for DLIO. The cloned ROS2 branch works with PointCloud2. CustomMsg support is a separate Livox branch upstream and would add more moving parts.

If your normal `msg_MID360_launch.py` currently publishes CustomMsg only, set the Livox driver's `xfer_format` back to PointCloud2 mode or use your existing CustomMsg-to-PointCloud2 converter. Native PointCloud2 from the Livox driver is preferred for the first test.

## Install system dependencies

On the Go2 Jetson:

```
sudo apt update
sudo apt install -y \
  libomp-dev \
  libpcl-dev \
  libeigen3-dev \
  ros-humble-pcl-ros \
  ros-humble-pcl-conversions \
  ros-humble-tf2-ros \
  ros-humble-nav-msgs \
  ros-humble-geometry-msgs \
  ros-humble-sensor-msgs
```

If `rosdep` is available, also run:

```
cd /home/aditya/Projects/Pedro_ws
rosdep install --from-paths direct_lidar_inertial_odometry --ignore-src -r -y
```

## Build DLIO

From the parent workspace:

```
cd /home/aditya/Projects/Pedro_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select direct_lidar_inertial_odometry
source install/setup.bash
```

If you prefer to keep DLIO in its own workspace instead of building from `Pedro_ws`, use this layout:

```
mkdir -p ~/dlio_ws/src
cp -r /home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry ~/dlio_ws/src/
cd ~/dlio_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select direct_lidar_inertial_odometry
source install/setup.bash
```

## If the build fails

### Missing `tf2_ros` or `pcl_conversions`

Install missing packages:

```
sudo apt install -y ros-humble-tf2-ros ros-humble-pcl-conversions
```

Then rebuild.

### Package not found by colcon

Check that the package is directly inside the workspace source path. For example, this is good:

```
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry/package.xml
```

This is also good in a separate workspace:

```
~/dlio_ws/src/direct_lidar_inertial_odometry/package.xml
```

Then run:

```
colcon list | grep direct_lidar_inertial_odometry
```

### ROS environment not sourced

Run:

```
source /opt/ros/humble/setup.bash
```

Then rebuild.

## Configure DLIO for the Go2

Go2-specific runtime config:

```
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry/cfg/params_go2_mid360.yaml
```

Important values:

```
frames/odom: odom
frames/baselink: base_link
frames/lidar: livox_frame
frames/imu: livox_imu
use_sim_time: false
```

Go2-specific extrinsic config:

```
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry/cfg/dlio_go2_mid360.yaml
```

Important values:

```
extrinsics/baselink2imu/t
extrinsics/baselink2imu/R
extrinsics/baselink2lidar/t
extrinsics/baselink2lidar/R
```

DLIO wants transforms from the robot center/body frame to the sensors:

```
base_link -> imu
base_link -> livox_frame
```

This is different from FAST-LIO, which uses the LiDAR-to-IMU extrinsic internally.

Start with rough measured values, then refine. If the LiDAR is mounted at the robot center and level, identity rotation and near-zero translation are acceptable for first testing, but not ideal.

## Run DLIO standalone first

Do not connect DLIO to Nav2 until this standalone test is stable.

Terminal 1: start Livox in PointCloud2 mode.

```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Check message types:

```
ros2 topic info /livox/lidar -v
ros2 topic hz /livox/lidar
ros2 topic hz /livox/imu
```

Expected:

```
/livox/lidar -> sensor_msgs/msg/PointCloud2
/livox/imu   -> sensor_msgs/msg/Imu
```

Terminal 2: run DLIO with the Go2 launch file.

If built from `/home/aditya/Projects/Pedro_ws`:

```
cd /home/aditya/Projects/Pedro_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch direct_lidar_inertial_odometry dlio_go2_mid360.launch.py \
  rviz:=false \
  pointcloud_topic:=/livox/lidar \
  imu_topic:=/livox/imu \
  odom_topic:=/odom
```

If built from `~/dlio_ws`:

```
source /opt/ros/humble/setup.bash
source ~/dlio_ws/install/setup.bash
ros2 launch direct_lidar_inertial_odometry dlio_go2_mid360.launch.py \
  rviz:=false \
  pointcloud_topic:=/livox/lidar \
  imu_topic:=/livox/imu \
  odom_topic:=/odom
```

## DLIO standalone validation

Check that DLIO is publishing odometry:

```
ros2 topic info /odom -v
ros2 topic hz /odom
ros2 run tf2_ros tf2_echo odom base_link
```

Stationary test:

```
ros2 topic echo /odom --field pose.pose.position
```

Expected:

- Robot physically stationary.
- `/odom` position should stay nearly constant for 60 seconds.
- A few centimeters of drift may be acceptable.
- Tens of centimeters or meters is not acceptable.

Pure rotation test:

- Slowly rotate the robot in place.
- Yaw should change.
- `x`, `y`, and `z` should not move much.

Slow translation test:

- Move forward slowly about 0.5 to 1.0 m.
- `/odom` should move in the correct direction.
- Stop and verify `/odom` does not continue drifting heavily.

If DLIO fails these tests, do not use it with Nav2 yet.

## Run Nav2 with DLIO odometry

Only do this after standalone DLIO odometry is stable.

Terminal 1:

```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Terminal 2:

```
cd /home/aditya/Projects/Pedro_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch direct_lidar_inertial_odometry dlio_go2_mid360.launch.py \
  rviz:=false \
  pointcloud_topic:=/livox/lidar \
  imu_topic:=/livox/imu \
  odom_topic:=/odom
```

Terminal 3:

```
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

Important:

- DLIO publishes `/odom`.
- DLIO publishes `odom -> base_link`.
- Go2 driver must not publish `/odom`.
- Go2 driver must not publish `odom -> base_link`.
- AMCL/Nav2 should publish `map -> odom` after the 2D Pose Estimate.

## Validate the Nav2 TF chain

Before giving a Nav2 goal:

```
ros2 topic info /odom -v
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo map odom
ros2 topic hz /scan
```

Expected:

- `/odom` publisher should be DLIO, not `go2_driver_node`.
- `odom -> base_link` should be stable while stationary.
- `map -> odom` should appear after AMCL accepts the 2D Pose Estimate.
- `/scan` should update continuously.

Then give a very close Nav2 goal first, such as 0.3 to 0.5 m forward.

## If Livox PointCloud2 does not work with DLIO

DLIO's ROS2 branch detects Livox PointCloud2 using point fields, especially the timestamp field. Check fields:

```
ros2 topic echo /livox/lidar --once
```

Look for fields similar to:

```
x, y, z, intensity, timestamp
```

If the PointCloud2 lacks usable point timestamps, DLIO may disable deskewing or perform poorly.

Try these in order:

1. Use native Livox PointCloud2 from the driver instead of a converter.
2. Confirm the Livox driver is publishing PointCloud2 with per-point timestamps.
3. Test with `odom/computeTimeOffset: false` in `params_go2_mid360.yaml`.
4. Test `pointcloud/deskew: false` in `dlio_go2_mid360.yaml` only as a diagnostic. This can reduce sync failures but may hurt motion accuracy.
5. If you must use Livox CustomMsg, evaluate the upstream `feature/livox-support` branch separately.

## Tuning notes for Go2 + MID-360

Config file:

```
/home/aditya/Projects/Pedro_ws/direct_lidar_inertial_odometry/cfg/params_go2_mid360.yaml
```

If CPU is overloaded or DLIO falls behind:

```
odom/preprocessing/voxelFilter/res: 0.25
odom/gicp/maxIterations: 32
```

If DLIO has too few points or weak matching indoors:

```
odom/preprocessing/voxelFilter/res: 0.15
odom/gicp/maxCorrespondenceDistance: 1.0
```

If Go2 body/legs contaminate the scan:

```
odom/preprocessing/cropBoxFilter/size: 1.0
```

If startup is unstable:

```
odom/imu/calibration/time: 8.0
```

Keep the robot completely still during the startup calibration period.

## Common failure cases

### `/odom` has two publishers

Check:

```
ros2 topic info /odom -v
```

Fix:

```
driver_odom_tf:=false
driver_odom_topic:=false
```

### `map` is missing from TF tree

AMCL has not accepted the 2D Pose Estimate yet, or Nav2 localization is not active.

Check:

```
ros2 node list | grep amcl
ros2 topic echo /amcl_pose --once
ros2 run tf2_ros tf2_echo map odom
```

### DLIO odometry drifts while stationary

Likely causes:

- Robot moved during IMU startup calibration.
- Wrong `base_link -> imu` or `base_link -> livox_frame` extrinsics.
- Livox PointCloud2 timestamps not suitable for deskewing.
- IMU/LiDAR timestamps not synchronized well enough.
- Too few geometric features.
- Vibration from the robot.

### Pure rotation creates fake translation

Likely causes:

- Wrong extrinsics.
- Wrong frame orientation.
- Bad timestamp/deskew behavior.
- LiDAR mostly seeing the floor or too little structure.

### Nav2 goes crazy after a goal but DLIO standalone was stable

Check for TF/topic conflicts first:

```
ros2 topic info /odom -v
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo map odom
```

Then check local costmap and scan:

```
ros2 topic hz /scan
ros2 topic echo /scan --once
```

If `/odom` is stable but `map -> odom` jumps, the problem is AMCL/localization. If `/odom` jumps, the problem is DLIO/odometry.

## Minimal success checklist

Before using DLIO for real Nav2 movement:

1. `/livox/lidar` is PointCloud2.
2. `/livox/imu` is publishing near 200 Hz.
3. DLIO is the only `/odom` publisher.
4. DLIO publishes a stable `odom -> base_link` while stationary.
5. Pure rotation does not create large fake x/y/z motion.
6. AMCL creates `map -> odom` after 2D Pose Estimate.
7. The full TF chain is `map -> odom -> base_link -> livox_frame`.
8. A tiny Nav2 goal works before attempting a longer goal.
