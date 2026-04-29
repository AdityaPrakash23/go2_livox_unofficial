# Steps to run the new setup with Livox Lidar

**Run these in your 1st terminal**
```
source ~/test_sdk_ws/install/setup.bash
export ROBOT_IP="192.168.123.161"
```

**Run this command in a new terminal**\
`ros2 run tf2_ros static_transform_publisher 0 0 0 3.14 0 0 base_link livox_frame`

**Then run the following in another new terminal**
```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

*Confirm that the livox lidar is connected*\
*Then go back to 1st terminal and run*\
`ros2 launch go2_robot_sdk robot.launch.py`

*The rviz window should show up with the robot and Lidar running and mapping happening*\
*Then use the SLAM toolbox plugin inside Rviz to save the map*\
