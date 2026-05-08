# Navigation launch file - optimized for AMCL localization and Nav2
# Usage: ros2 launch go2_robot_sdk navigation.launch.py map:=/path/to/map.yaml

import os
from typing import List
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import FrontendLaunchDescriptionSource, PythonLaunchDescriptionSource


def generate_launch_description():
    """Generate launch description for Go2 navigation mode"""
    
    # Environment variables
    robot_token = os.getenv('ROBOT_TOKEN', '')
    robot_ip = os.getenv('ROBOT_IP', '')
    robot_ip_list = robot_ip.replace(" ", "").split(",") if robot_ip else []
    map_file = os.getenv('MAP_FILE', '')
    conn_type = os.getenv('CONN_TYPE', 'webrtc')
    livox_cloud_topic = os.getenv('LIVOX_CLOUD_TOPIC', '/livox/lidar')
    livox_imu_topic = os.getenv('LIVOX_IMU_TOPIC', '/livox/imu')
    livox_frame = os.getenv('LIVOX_FRAME', 'livox_frame')
    
    # Determine connection mode
    conn_mode = "single" if len(robot_ip_list) == 1 and conn_type != "cyclonedds" else "multi"
    
    # Package paths
    package_dir = get_package_share_directory('go2_robot_sdk')
    urdf_file = 'go2.urdf' if conn_mode == 'single' else 'multi_go2.urdf'
    rviz_config = 'single_robot_conf.rviz' if conn_mode == 'single' else 'multi_robot_conf.rviz'
    
    config_paths = {
        'joystick': os.path.join(package_dir, 'config', 'joystick.yaml'),
        'twist_mux': os.path.join(package_dir, 'config', 'twist_mux.yaml'),
        'livox_ekf': os.path.join(package_dir, 'config', 'livox_ekf.yaml'),
        'nav2': os.path.join(package_dir, 'config', 'nav2_params.yaml'),
        'rviz': os.path.join(package_dir, 'config', rviz_config),
        'urdf': os.path.join(package_dir, 'urdf', urdf_file),
    }
    
    print(f"🧭 Go2 Navigation Mode:")
    print(f"   Robot IPs: {robot_ip_list}")
    print(f"   Connection: {conn_type} ({conn_mode})")
    
    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    map_arg = LaunchConfiguration('map')
    with_rviz = LaunchConfiguration('rviz', default='true')
    with_foxglove = LaunchConfiguration('foxglove', default='true')
    with_joystick = LaunchConfiguration('joystick', default='true')
    with_go2_lidar = LaunchConfiguration('go2_lidar', default='false')
    with_ekf = LaunchConfiguration('use_ekf', default='true')
    
    launch_args = [
        DeclareLaunchArgument(
            'map',
            default_value=map_file,
            description='Full path to map yaml file for navigation'
        ),
        DeclareLaunchArgument('rviz', default_value='true', description='Launch RViz2'),
        DeclareLaunchArgument('foxglove', default_value='false', description='Launch Foxglove Bridge'),
        DeclareLaunchArgument('joystick', default_value='true', description='Launch joystick control'),
        DeclareLaunchArgument('use_ekf', default_value='true', description='Fuse Go2 odometry and Livox IMU with robot_localization'),
        DeclareLaunchArgument('driver_odom_tf', default_value='false', description='Let the Go2 driver publish odom -> base_link TF'),
        DeclareLaunchArgument('go2_lidar', default_value='false', description='Run the built-in Go2 lidar processing pipeline'),
        DeclareLaunchArgument('navigation_cloud_topic', default_value=livox_cloud_topic, description='Livox PointCloud2 topic used for navigation'),
        DeclareLaunchArgument('livox_imu_topic', default_value=livox_imu_topic, description='Livox sensor_msgs/Imu topic used by the EKF'),
        DeclareLaunchArgument('livox_frame', default_value=livox_frame, description='Livox lidar frame id'),
        DeclareLaunchArgument('livox_x', default_value='0.0', description='Livox x offset from base_link in meters'),
        DeclareLaunchArgument('livox_y', default_value='0.0', description='Livox y offset from base_link in meters'),
        DeclareLaunchArgument('livox_z', default_value='0.0', description='Livox z offset from base_link in meters'),
        DeclareLaunchArgument('livox_roll', default_value='3.14', description='Livox roll offset from base_link in radians'),
        DeclareLaunchArgument('livox_pitch', default_value='0.0', description='Livox pitch offset from base_link in radians'),
        DeclareLaunchArgument('livox_yaw', default_value='0.0', description='Livox yaw offset from base_link in radians'),
    ]
    
    # Load URDF
    with open(config_paths['urdf'], 'r') as file:
        robot_desc = file.read()
    
    # Core nodes
    core_nodes = [
        # Robot state publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='go2_robot_state_publisher',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'robot_description': robot_desc
            }],
        ),
        # Main robot driver
        Node(
            package='go2_robot_sdk',
            executable='go2_driver_node',
            name='go2_driver_node',
            output='screen',
            parameters=[{
                'robot_ip': robot_ip,
                'token': robot_token,
                'conn_type': conn_type,
                'publish_odom_tf': LaunchConfiguration('driver_odom_tf'),
            }],
        ),
        # Livox lidar mounting transform. Replace these launch argument defaults
        # with the measured position/orientation of the sensor on your robot.
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_link_to_livox',
            arguments=[
                '--x', LaunchConfiguration('livox_x'),
                '--y', LaunchConfiguration('livox_y'),
                '--z', LaunchConfiguration('livox_z'),
                '--roll', LaunchConfiguration('livox_roll'),
                '--pitch', LaunchConfiguration('livox_pitch'),
                '--yaw', LaunchConfiguration('livox_yaw'),
                '--frame-id', 'base_link',
                '--child-frame-id', LaunchConfiguration('livox_frame'),
            ],
            output='screen',
        ),
        # EKF odometry. The Go2 driver still publishes /odom, but the EKF owns
        # odom -> base_link TF when use_ekf is true.
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            condition=IfCondition(with_ekf),
            output='screen',
            parameters=[
                config_paths['livox_ekf'],
                {'imu0': LaunchConfiguration('livox_imu_topic')},
                {'use_sim_time': use_sim_time},
            ],
        ),
        # Built-in Go2 lidar processing node. Off by default for Livox navigation.
        Node(
            package='lidar_processor_cpp',
            executable='lidar_to_pointcloud_node',
            name='lidar_to_pointcloud',
            condition=IfCondition(with_go2_lidar),
            remappings=[
                ('robot0/point_cloud2', 'point_cloud2'),
            ] if conn_mode == 'single' else [],
            parameters=[{
                'robot_ip_lst': robot_ip_list,
                'map_name': '3d_map',
                'map_save': 'false'  # Don't save during navigation
            }],
        ),
        # Point cloud aggregator - optimized for real-time navigation
        Node(
            package='lidar_processor_cpp',
            executable='pointcloud_aggregator_node',
            name='pointcloud_aggregator',
            condition=IfCondition(with_go2_lidar),
            parameters=[{
                'max_range': 20.0,
                'min_range': 0.1,
                'height_filter_min': -2.0,
                'height_filter_max': 3.0,
                'downsample_rate': 1,
                'publish_rate': 30.0
            }],
        ),
        # PointCloud to LaserScan converter - optimized for real-time
        Node(
            package='pointcloud_to_laserscan',
            executable='pointcloud_to_laserscan_node',
            name='go2_pointcloud_to_laserscan',
            remappings=[
                ('cloud_in', LaunchConfiguration('navigation_cloud_topic')),
                ('scan', '/scan'),
            ],
            parameters=[{
                # 'target_frame': 'base_link',
                # 'max_height': 2.0,
                # 'min_height': -0.2,
                # 'angle_min': -3.14159,
                # 'angle_max': 3.14159,
                # 'angle_increment': 0.00872665,
                # 'scan_time': 0.1,
                # 'range_min': 0.1,
                # 'range_max': 20.0,
                # 'use_inf': True,
                # 'concurrency_level': 1,
                'target_frame': 'base_link',
                'max_height': 0.5,
                'min_height': 0.1,
                'range_min': 0.5,
                'angle_min': -3.14159,
                'angle_max': 3.14159,
                'angle_increment': 0.0174533,
            }],
            output='screen',
        ),
        # TTS Node
        Node(
            package='speech_processor',
            executable='tts_node',
            name='tts_node',
            parameters=[{
                'api_key': os.getenv('ELEVENLABS_API_KEY', ''),
                'provider': 'elevenlabs',
                'voice_name': 'XrExE9yKIg1WjnnlVkGX',
                'local_playback': False,
                'use_cache': True,
                'audio_quality': 'standard'
            }],
        ),
    ]
    
    # Teleop nodes
    teleop_nodes = [
        Node(
            package='joy',
            executable='joy_node',
            condition=IfCondition(with_joystick),
            parameters=[config_paths['joystick']]
        ),
        Node(
            package='teleop_twist_joy',
            executable='teleop_node',
            name='go2_teleop_node',
            condition=IfCondition(with_joystick),
            parameters=[config_paths['twist_mux']],
        ),
        Node(
            package='twist_mux',
            executable='twist_mux',
            output='screen',
            parameters=[
                {'use_sim_time': use_sim_time},
                config_paths['twist_mux']
            ],
        ),
    ]
    
    # Visualization nodes
    viz_nodes = [
        Node(
            package='rviz2',
            executable='rviz2',
            condition=IfCondition(with_rviz),
            name='go2_rviz2',
            output='screen',
            arguments=['-d', config_paths['rviz']],
            parameters=[{'use_sim_time': False}]
        ),
    ]
    
    # Include launches
    foxglove_launch = os.path.join(
        get_package_share_directory('foxglove_bridge'),
        'launch', 'foxglove_bridge_launch.xml'
    )
    
    include_launches = [
        # Foxglove Bridge
        IncludeLaunchDescription(
            FrontendLaunchDescriptionSource(foxglove_launch),
            condition=IfCondition(with_foxglove),
        ),
        # AMCL Localization
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                os.path.join(get_package_share_directory('nav2_bringup'),
                            'launch', 'localization_launch.py')
            ]),
            launch_arguments={
                'map': map_arg,
                'params_file': config_paths['nav2'],
                'use_sim_time': use_sim_time,
            }.items(),
        ),
        # Nav2 Navigation
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                os.path.join(get_package_share_directory('nav2_bringup'),
                            'launch', 'navigation_launch.py')
            ]),
            launch_arguments={
                'params_file': config_paths['nav2'],
                'use_sim_time': use_sim_time,
            }.items(),
        ),
    ]
    
    return LaunchDescription(
        launch_args +
        core_nodes +
        teleop_nodes +
        viz_nodes +
        include_launches
    )
