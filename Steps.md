# Steps to build the package incase of updates

*Run these commands in a terminal*
```
cd ~/test_sdk_ws
colcon build --packages-select go2_robot_sdk
source install/setup.bash
```

# Steps to run the new setup with Livox Lidar

**Run these in your 1st terminal**
```
source ~/test_sdk_ws/install/setup.bash
export ROBOT_IP="192.168.123.161"
```

**Note: No need to run the above 2 commands as they run by default when a new terminal session is openned**\

*Run this command in a new terminal*\
`ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 base_link livox_frame`

**Note: Avoid running the above command unless things in rviz don't work properly**\

*Then run the following in another new terminal*
```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```


*Confirm that the livox lidar is connected*\
*Then go back to 1st terminal and run*\
`ros2 launch go2_robot_sdk robot.launch.py   mapping_cloud_topic:=/livox/lidar   livox_imu_topic:=/livox/imu   livox_frame:=livox_frame`

*The rviz window should show up with the robot and Lidar running and mapping happening*\
*Then use the SLAM toolbox plugin inside Rviz to save the map*\

*Command to run teleop to do map creation without the camepad for Go2 and have finer speed control*
`ros2 run teleop_twist_keyboard teleop_twist_keyboard`

*For running Nav2, run the following command after running the livox launch file*\
`ros2 launch go2_robot_sdk navigation.launch.py map:=/home/orin/test_sdk_ws/testLab.yaml driver_odom_tf:=false`



*New commands*
```
ros2 launch livox_ros_driver2 msg_MID360_launch.py

ros2 launch fast_lio mapping.launch.py

ros2 launch go2_robot_sdk navigation.launch.py \
  map:=/home/orin/test_sdk_ws/testLab.yaml \
  use_livox_custom_to_pointcloud2:=true \
  livox_custom_topic:=/livox/lidar \
  livox_pointcloud2_topic:=/livox/points \
  navigation_cloud_topic:=/livox/points \
  livox_converter_reliability:=best_effort \
  livox_converter_publish_period:=0.2 \
  use_fast_lio_odom:=true \
  fast_lio_odom_topic:=/Odometry \
  adapted_odom_topic:=/odom \
  driver_odom_tf:=false \
  restamp_sensor_data:=true \
  foxglove:=false \
  enable_video:=false


```

# Steps to run mapping with Livox + FAST-LIO odometry

This mapping path is meant to avoid using the Unitree Go2 odometry while building a Nav2 map. FAST-LIO provides `odom -> base_link`, SLAM Toolbox provides `map -> odom`, and the Livox point cloud is converted into `/scan` for 2D mapping.

## 1. Start the Livox MID-360 driver in CustomMsg mode

Run the Livox driver so `/livox/lidar` publishes `livox_ros_driver2/msg/CustomMsg`. FAST-LIO needs this CustomMsg stream.

```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Check the message type:

```
ros2 topic info /livox/lidar -v
ros2 topic echo /livox/lidar livox_ros_driver2/msg/CustomMsg --once
```

Do not run a separate `static_transform_publisher` for `base_link -> livox_frame` when using the new `go2_robot_sdk mapping.launch.py`, because that launch file already publishes the static Livox mounting transform. Pass the measured Livox pose using `livox_x`, `livox_y`, `livox_z`, `livox_roll`, `livox_pitch`, and `livox_yaw` if the default `0 0 0 0 0 0` is not correct.

## 2. Start FAST-LIO2 mapping/odometry

Run the FAST-LIO2 launch file after the Livox CustomMsg stream is active.

```
source /opt/ros/humble/setup.bash
source ~/FAST_LIO_ROS2/install/setup.bash
ros2 launch fast_lio mapping.launch.py
```

Check that FAST-LIO is publishing odometry. Use the topic that your FAST-LIO repo actually publishes.

```
ros2 topic hz /Odometry
ros2 topic echo /Odometry --once
```

If your FAST-LIO odometry topic is `/lio_sam_ros2/mapping/odometry`, use that topic in the mapping launch command below instead of `/Odometry`.

## 3. Start Go2 SLAM mapping with FAST-LIO odometry

This launch starts RViz2, the Go2 driver, the Livox CustomMsg-to-PointCloud2 converter, `pointcloud_to_laserscan`, the FAST-LIO odom adapter, and SLAM Toolbox.

```
source /opt/ros/humble/setup.bash
source ~/test_sdk_ws/install/setup.bash
export ROBOT_IP="192.168.123.161"

ros2 launch go2_robot_sdk mapping.launch.py \
  driver_odom_tf:=false \
  use_fast_lio_odom:=true \
  fast_lio_odom_topic:=/Odometry \
  adapted_odom_topic:=/odom \
  use_livox_custom_to_pointcloud2:=true \
  livox_custom_topic:=/livox/lidar \
  livox_pointcloud2_topic:=/livox/points \
  mapping_cloud_topic:=/livox/points \
  livox_converter_frame_id:=livox_frame \
  livox_converter_reliability:=best_effort \
  foxglove:=false \
  enable_video:=false
```

If FAST-LIO publishes `/lio_sam_ros2/mapping/odometry`, change the command to:

```
fast_lio_odom_topic:=/lio_sam_ros2/mapping/odometry
```

## 4. Verify the TF and topic chain

The expected TF chain during mapping is:

```
map -> odom -> base_link -> livox_frame
```

Run these checks before driving far:

```
ros2 topic hz /livox/points
ros2 topic hz /scan
ros2 topic hz /odom
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo map odom
```

`odom -> base_link` should come from the FAST-LIO odom adapter. `map -> odom` should appear after SLAM Toolbox is running. Do not allow the Go2 driver and FAST-LIO adapter to both publish `odom -> base_link` at the same time.


# New Steps for running setup:

Open 3 terminals. In terminal 1 run 
```
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```
In the 2nd terminal run
```
ros2 launch fast_lio mapping.launch.py
```
In the 3rd terminal run
```
ros2 launch go2_robot_sdk navigation.launch.py \
  map:=/home/orin/test_sdk_ws/testLab.yaml \
  use_livox_custom_to_pointcloud2:=true \
  livox_custom_topic:=/livox/lidar \
  livox_pointcloud2_topic:=/livox/points \
  navigation_cloud_topic:=/livox/points \
  use_fast_lio_odom:=true \
  fast_lio_odom_topic:=/Odometry \
  adapted_odom_topic:=/odom \
  driver_odom_tf:=false \
  driver_odom_topic:=false \
  foxglove:=false \
  enable_video:=false
```

# Fallback order for stable Nav2 odometry/localization

Use this section when FAST-LIO odometry is unstable, the robot jitters while stationary, or the robot moves normally at first and then goes far outside the map after a Nav2 goal.

Nav2 needs this TF chain:

```
map -> odom -> base_link -> livox_frame
```

The source of `odom -> base_link` can be changed. AMCL/Nav2 still publishes or uses `map -> odom`; the odometry source only provides the short-term local motion estimate.

## Fallback 1: Get Nav2 working again with Go2 odometry

This is the operational fallback. Use it when you need the robot to navigate now and FAST-LIO is not trustworthy.

In terminal 1, start the Livox MID-360 in PointCloud2 mode. For AMCL and Nav2, the Livox data must be available as `sensor_msgs/msg/PointCloud2`.

```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Check that `/livox/lidar` is publishing PointCloud2:

```
ros2 topic info /livox/lidar -v
ros2 topic hz /livox/lidar
```

In terminal 2, start Nav2 using the Go2 driver's own odometry and TF:

```
source /opt/ros/humble/setup.bash
source ~/test_sdk_ws/install/setup.bash
export ROBOT_IP="192.168.123.161"

ros2 launch go2_robot_sdk navigation.launch.py \   
  map:=/home/orin/trimbleLab.yaml \
  use_livox_custom_to_pointcloud2:=true \
  livox_custom_topic:=/livox/lidar \
  livox_pointcloud2_topic:=/livox/points \
  navigation_cloud_topic:=/livox/points \
  use_fast_lio_odom:=false \
  fast_lio_odom_topic:=/Odometry \
  adapted_odom_topic:=/odom \
  driver_odom_tf:=true \
  driver_odom_topic:=true \
  foxglove:=false \
  enable_video:=false
```

Use this if FAST-LIO is producing bad `/Odometry`, `No Effective Points!`, or large jumps. The Go2 odometry may lag or drift, but it is often safer than unstable LIO odometry.

Validation checks:

```
ros2 topic info /odom -v
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo map odom
ros2 topic hz /scan
```

Expected result:

- `/odom` publisher should be `go2_driver_node`.
- `odom -> base_link` should update smoothly, not jump meters while stationary.
- `map -> odom` appears after AMCL receives the 2D Pose Estimate.
- `/scan` should update continuously.

Do not run FAST-LIO in this fallback. Do not let both Go2 odometry and FAST-LIO publish `/odom` or `odom -> base_link` at the same time.

## Fallback 2: Repair and re-test FAST-LIO before using it with Nav2

Use this path when you want FAST-LIO odometry again, but only test FAST-LIO by itself first. Do not connect it to Nav2 until it passes the stationary and rotation tests.

In terminal 1, run Livox in CustomMsg mode:

```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Check that the topic is `livox_ros_driver2/msg/CustomMsg`:

```
ros2 topic info /livox/lidar -v
ros2 topic echo /livox/lidar livox_ros_driver2/msg/CustomMsg --once
ros2 topic hz /livox/lidar
ros2 topic hz /livox/imu
```

In terminal 2, run FAST-LIO:

```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch fast_lio mapping.launch.py
```

Check FAST-LIO odometry:

```
ros2 topic hz /Odometry
ros2 topic echo /Odometry --field pose.pose.position
ros2 run tf2_ros tf2_echo camera_init body
```

Stationary test:

- Put the robot still on the floor.
- Watch `/Odometry` for at least 60 seconds.
- `x`, `y`, and `z` should only move by a few centimeters.
- If the values drift by tens of centimeters or meters while stationary, do not use FAST-LIO for Nav2.

Rotation test:

- Rotate the robot slowly in place.
- `x`, `y`, and `z` should stay roughly stable.
- Yaw should change.
- If pure rotation causes large translation, the likely cause is LiDAR-IMU extrinsic calibration, wrong Livox mounting transform, wrong axis convention, or timestamp/deskewing trouble.

Feature test:

- Run FAST-LIO in a feature-rich area with walls, desks, shelves, or other geometry.
- Avoid open empty space, glass-heavy areas, and pointing mostly at the floor.
- `No Effective Points!` while completely stationary can happen occasionally.
- Repeated `No Effective Points!` during slow movement means FAST-LIO is not getting enough usable geometry or the preprocessing/extrinsic settings are wrong.

If FAST-LIO passes the tests, then connect it to Nav2:

```
ros2 launch go2_robot_sdk navigation.launch.py \
  map:=/home/orin/test_sdk_ws/testLab.yaml \
  use_livox_custom_to_pointcloud2:=true \
  livox_custom_topic:=/livox/lidar \
  livox_pointcloud2_topic:=/livox/points \
  navigation_cloud_topic:=/livox/points \
  use_fast_lio_odom:=true \
  fast_lio_odom_topic:=/Odometry \
  adapted_odom_topic:=/odom \
  driver_odom_tf:=false \
  driver_odom_topic:=false \
  foxglove:=false \
  enable_video:=false
```

Validation checks before sending a Nav2 goal:

```
ros2 topic info /odom -v
ros2 topic info /Odometry -v
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo map odom
```

Expected result:

- `/Odometry` should come from FAST-LIO.
- `/odom` should come from the FAST-LIO odom adapter, not `go2_driver_node`.
- `odom -> base_link` should be smooth.
- `map -> odom` should appear after AMCL accepts the 2D Pose Estimate.

If `/odom` is still published by `go2_driver_node`, relaunch with:

```
driver_odom_tf:=false
driver_odom_topic:=false
```

## Fallback 3: Replace FAST-LIO with DLIO

DLIO is the recommended backup LIO package to try if FAST-LIO remains unstable. It can work with ROS2, Livox PointCloud2 data, and IMU data, which makes it a cleaner backup path than ROS1-only Livox LIO packages.

Suggested workspace:

```
mkdir -p ~/dlio_ws/src
cd ~/dlio_ws/src
git clone https://github.com/vectr-ucla/direct_lidar_inertial_odometry.git
cd direct_lidar_inertial_odometry
git checkout feature/ros2
```

Install dependencies using the instructions from the DLIO repository. Then build:

```
cd ~/dlio_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Run Livox in PointCloud2 mode:

```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Check the topics:

```
ros2 topic info /livox/lidar -v
ros2 topic hz /livox/lidar
ros2 topic hz /livox/imu
```

Configure DLIO so the important frames and topics match the Go2/Nav2 setup:

```
pointcloud_topic: /livox/lidar
imu_topic: /livox/imu
odom_frame: odom
base_frame: base_link
```

If DLIO has a separate LiDAR frame parameter, set it to:

```
livox_frame
```

The expected DLIO output should provide odometry and/or TF equivalent to:

```
odom -> base_link
```

Before connecting DLIO to Nav2, run the same standalone tests used for FAST-LIO:

```
ros2 topic hz /odom
ros2 topic echo /odom --field pose.pose.position
ros2 run tf2_ros tf2_echo odom base_link
```

Stationary test:

- Leave the robot still for at least 60 seconds.
- `/odom` should not drift significantly.

Rotation test:

- Rotate slowly in place.
- Yaw should change.
- `x`, `y`, and `z` should remain mostly stable.

If DLIO publishes odometry on a topic other than `/odom`, remap that topic to `/odom` or reuse the existing odometry adapter pattern. The final Nav2 chain should still be:

```
map -> odom -> base_link -> livox_frame
```

Then run Nav2 with Go2 odometry disabled:

```
ros2 launch go2_robot_sdk navigation.launch.py \
  map:=/home/orin/test_sdk_ws/testLab.yaml \
  use_fast_lio_odom:=false \
  driver_odom_tf:=false \
  driver_odom_topic:=false \
  navigation_cloud_topic:=/livox/lidar \
  foxglove:=false \
  enable_video:=false
```

Only use this command if DLIO itself is already publishing `/odom` and `odom -> base_link`. If DLIO publishes a different odometry topic, add a small adapter/remap first so Nav2 receives `/odom`.

## Decision rule

Use this order during testing:

1. If the robot must navigate today, use Go2 odometry and Livox PointCloud2 with AMCL/Nav2.
2. If you want better odometry, test FAST-LIO alone until it is stable while stationary and during pure rotation.
3. If FAST-LIO keeps producing jumps or repeated `No Effective Points!`, try DLIO as the backup LIO source.
4. Do not give Nav2 a goal until `odom -> base_link` is stable while the robot is stationary.
5. Never allow two nodes to publish `/odom` or `odom -> base_link` at the same time.
