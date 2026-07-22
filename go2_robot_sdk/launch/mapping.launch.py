# Mapping launch file - optimized for SLAM and map creation
# Usage: ros2 launch go2_robot_sdk mapping.launch.py

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
    """Generate launch description for Go2 mapping mode"""
    
    # Environment variables
    robot_token = os.getenv('ROBOT_TOKEN', '')
    robot_ip = os.getenv('ROBOT_IP', '')
    robot_ip_list = robot_ip.replace(" ", "").split(",") if robot_ip else []
    map_name = os.getenv('MAP_NAME', 'my_map')
    save_map = os.getenv('MAP_SAVE', 'true')
    conn_type = os.getenv('CONN_TYPE', 'webrtc')
    livox_cloud_topic = os.getenv('LIVOX_CLOUD_TOPIC', '/livox/lidar')
    livox_imu_topic = os.getenv('LIVOX_IMU_TOPIC', '/livox/imu')
    livox_frame = os.getenv('LIVOX_FRAME', 'livox_frame')
    converted_livox_topic = os.getenv('LIVOX_POINTCLOUD2_TOPIC', '/livox/points')
    
    # Determine connection mode
    conn_mode = "single" if len(robot_ip_list) == 1 and conn_type != "cyclonedds" else "multi"
    
    # Package paths
    package_dir = get_package_share_directory('go2_robot_sdk')
    urdf_file = 'go2.urdf' if conn_mode == 'single' else 'multi_go2.urdf'
    rviz_config = 'single_robot_conf.rviz' if conn_mode == 'single' else 'multi_robot_conf.rviz'
    
    config_paths = {
        'joystick': os.path.join(package_dir, 'config', 'joystick.yaml'),
        'twist_mux': os.path.join(package_dir, 'config', 'twist_mux.yaml'),
        'slam': os.path.join(package_dir, 'config', 'mapper_params_online_async.yaml'),
        'rviz': os.path.join(package_dir, 'config', rviz_config),
        'urdf': os.path.join(package_dir, 'urdf', urdf_file),
    }
    
    print(f"🗺️  Go2 Mapping Mode:")
    print(f"   Robot IPs: {robot_ip_list}")
    print(f"   Connection: {conn_type} ({conn_mode})")
    print(f"   Map name: {map_name}")
    
    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    with_rviz = LaunchConfiguration('rviz', default='true')
    with_foxglove = LaunchConfiguration('foxglove', default='false')
    with_joystick = LaunchConfiguration('joystick', default='true')
    with_go2_lidar = LaunchConfiguration('go2_lidar', default='false')
    enable_video = LaunchConfiguration('enable_video', default='false')
    use_livox_custom_to_pointcloud2 = LaunchConfiguration('use_livox_custom_to_pointcloud2', default='true')
    use_fast_lio_odom = LaunchConfiguration('use_fast_lio_odom', default='true')
    
    launch_args = [
        DeclareLaunchArgument('use_sim_time', default_value='false', description='Use simulation clock'),
        DeclareLaunchArgument('rviz', default_value='true', description='Launch RViz2'),
        DeclareLaunchArgument('foxglove', default_value='false', description='Launch Foxglove Bridge'),
        DeclareLaunchArgument('joystick', default_value='true', description='Launch joystick control'),
        DeclareLaunchArgument('enable_video', default_value='false', description='Enable Go2 camera video publishing'),
        DeclareLaunchArgument('driver_odom_tf', default_value='false', description='Let the Go2 driver publish odom -> base_link TF'),
        DeclareLaunchArgument('go2_lidar', default_value='false', description='Run the built-in Go2 lidar processing pipeline'),
        DeclareLaunchArgument('mapping_cloud_topic', default_value=converted_livox_topic, description='PointCloud2 topic converted to /scan for SLAM Toolbox'),
        DeclareLaunchArgument('use_livox_custom_to_pointcloud2', default_value='true', description='Convert Livox CustomMsg into PointCloud2 for SLAM Toolbox'),
        DeclareLaunchArgument('livox_custom_topic', default_value=livox_cloud_topic, description='Livox CustomMsg topic used by FAST-LIO2 and the PointCloud2 converter'),
        DeclareLaunchArgument('livox_pointcloud2_topic', default_value=converted_livox_topic, description='Converted Livox PointCloud2 topic for SLAM Toolbox'),
        DeclareLaunchArgument('livox_converter_frame_id', default_value='', description='Optional frame_id override for converted Livox PointCloud2; empty preserves the CustomMsg frame'),
        DeclareLaunchArgument('use_fast_lio_odom', default_value='true', description='Adapt FAST-LIO2 /Odometry into /odom and publish odom -> base_link TF'),
        DeclareLaunchArgument('fast_lio_odom_topic', default_value='/Odometry', description='FAST-LIO2 nav_msgs/Odometry topic'),
        DeclareLaunchArgument('adapted_odom_topic', default_value='/odom', description='SLAM/Nav2 odometry topic published by the FAST-LIO adapter'),
        DeclareLaunchArgument('livox_imu_topic', default_value=livox_imu_topic, description='Livox sensor_msgs/Imu topic used by FAST-LIO2'),
        DeclareLaunchArgument('livox_frame', default_value=livox_frame, description='Livox lidar frame id'),
        DeclareLaunchArgument('livox_x', default_value='0.0', description='Livox x offset from base_link in meters'),
        DeclareLaunchArgument('livox_y', default_value='0.0', description='Livox y offset from base_link in meters'),
        DeclareLaunchArgument('livox_z', default_value='0.0', description='Livox z offset from base_link in meters'),
        DeclareLaunchArgument('livox_roll', default_value='0.0', description='Livox roll offset from base_link in radians'),
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
                'enable_video': enable_video,
                'publish_odom_tf': LaunchConfiguration('driver_odom_tf'),
            }],
        ),
        # Livox lidar mounting transform. Replace these defaults with the
        # measured position/orientation of the MID-360 on the robot.
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
        # Dual Livox stream for mapping: CustomMsg feeds FAST-LIO2 externally,
        # and this converted PointCloud2 feeds pointcloud_to_laserscan.
        Node(
            package='go2_robot_sdk',
            executable='livox_custom_to_pointcloud2',
            name='livox_custom_to_pointcloud2',
            condition=IfCondition(use_livox_custom_to_pointcloud2),
            output='screen',
            parameters=[{
                'input_topic': LaunchConfiguration('livox_custom_topic'),
                'output_topic': LaunchConfiguration('livox_pointcloud2_topic'),
                'frame_id': LaunchConfiguration('livox_converter_frame_id'),
                'reliability': 'reliable',
            }],
        ),
        # FAST-LIO2 should publish /Odometry. This adapter exposes the odom
        # topic/TF contract expected by SLAM Toolbox: odom -> base_link.
        Node(
            package='go2_robot_sdk',
            executable='fast_lio_odom_adapter',
            name='fast_lio_odom_adapter',
            condition=IfCondition(use_fast_lio_odom),
            output='screen',
            parameters=[{
                'input_topic': LaunchConfiguration('fast_lio_odom_topic'),
                'output_topic': LaunchConfiguration('adapted_odom_topic'),
                'odom_frame': 'odom',
                'base_frame': 'base_link',
                'publish_tf': True,
            }],
        ),
        # LiDAR processing node
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
                'map_name': map_name,
                'map_save': save_map
            }],
        ),
        # Point cloud aggregator - maximized for full coverage
        Node(
            package='lidar_processor_cpp',
            executable='pointcloud_aggregator_node',
            name='pointcloud_aggregator',
            condition=IfCondition(with_go2_lidar),
            parameters=[{
                'max_range': 20.0,
                'min_range': 0.3,
                'height_filter_min': -1.0,
                'height_filter_max': 3.0,
                'downsample_rate': 1,
                'publish_rate': 20.0
            }],
        ),
        # PointCloud to LaserScan converter - maximum coverage
        Node(
            package='pointcloud_to_laserscan',
            executable='pointcloud_to_laserscan_node',
            name='go2_pointcloud_to_laserscan',
            remappings=[
                ('cloud_in', LaunchConfiguration('mapping_cloud_topic')),
                ('scan', '/scan'),
            ],
            parameters=[{
                'target_frame': 'base_link',
                'max_height': 0.45,
                'min_height': 0.05,
                'angle_min': -3.14159,
                'angle_max': 3.14159,
                'angle_increment': 0.00872665,
                'scan_time': 0.1,
                'range_min': 0.2,
                'range_max': 5.0,
                'use_inf': False,
                'lazy': False,
                'concurrency_level': 2,
                'qos_overrides': {
                    '/scan': {
                        'publisher': {
                            'reliability': 'reliable',
                            'history': 'keep_last',
                            'depth': 10,
                        },
                    },
                },
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
            condition=IfCondition(with_joystick),
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
        # SLAM Toolbox for mapping
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                os.path.join(get_package_share_directory('slam_toolbox'),
                            'launch', 'online_async_launch.py')
            ]),
            launch_arguments={
                'slam_params_file': config_paths['slam'],
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
