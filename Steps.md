# Steps to run the new setup with Livox Lidar

**To build package after updates**
```
cd ~/test_sdk_ws/
colcon build --packges-select go2_robot_sdk
```

**Run these in your 1st terminal**
```
source ~/test_sdk_ws/install/setup.bash
export ROBOT_IP="192.168.123.161"
```

**Run this command in a new terminal**\
`ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 base_link livox_frame`

**Then run the following in another new terminal**
```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

*Confirm that the livox lidar is connected*\
*Then go back to 1st terminal and run*\
```
ros2 launch go2_robot_sdk robot.launch.py \
  mapping_cloud_topic:=/livox/lidar \
  livox_imu_topic:=/livox/imu \
  livox_frame:=livox_frame \
  use_ekf:=true \
  driver_odom_tf:=false
```

*The rviz window should show up with the robot and Lidar running and mapping happening*\
*Then use the SLAM toolbox plugin inside Rviz to save the map*\

**For running Navigation, end the last command and the static transform publisher command**\
**and run the following command in the same terminal**
```
ros2 launch go2_robot_sdk navigation.launch.py \
  map:=testLab.yaml \
  navigation_cloud_topic:=/livox/lidar \
  livox_imu_topic:=/livox/imu \
  livox_frame:=livox_frame \
  livox_x:=0.0 livox_y:=0.0 livox_z:=0.0 \
  livox_roll:=0.0 livox_pitch:=0.0 livox_yaw:=0.0
```
*Adjust the livox_x,livox_y,livox_z params*

