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
orin@orin:~$ ros2 launch livox_ros_driver2 msg_MID360_launch.py

orin@orin:~$ ros2 launch fast_lio mapping.launch.py ^C

orin@orin:~$ ros2 launch go2_robot_sdk navigation.launch.py   map:=/home/orin/test_sdk_ws/testLab.yaml   use_livox_custom_to_pointcloud2:=true   livox_custom_topic:=/livox/lidar   livox_pointcloud2_topic:=/livox/points   navigation_cloud_topic:=/livox/points   use_fast_lio_odom:=true   fast_lio_odom_topic:=/Odometry   adapted_odom_topic:=/odom   driver_odom_tf:=false   foxglove:=false   enable_video:=false


```