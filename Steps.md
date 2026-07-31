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