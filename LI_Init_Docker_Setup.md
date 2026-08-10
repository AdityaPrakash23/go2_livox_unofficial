# LI-Init Docker setup for Livox MID-360 calibration on Go2

This guide is for calibrating the Livox MID-360 LiDAR and its built-in IMU using LI-Init from a Jetson/Go2 computer running Ubuntu 22.04. Ubuntu 22.04 does not support ROS1 Noetic natively, so the practical path is to run ROS1 Noetic inside Docker.

Useful upstream references:

- LI-Init: https://github.com/hku-mars/LiDAR_IMU_Init
- Livox ROS Driver 2: https://github.com/Livox-SDK/livox_ros_driver2
- Livox SDK2: https://github.com/Livox-SDK/Livox-SDK2

LI-Init is only used for calibration. After calibration, copy the resulting `extrinsic_R`, `extrinsic_T`, and time offset into the ROS2 FAST-LIO config used by Nav2.

## What LI-Init calibrates

LI-Init estimates the transform and time offset between the LiDAR and IMU used by the LIO algorithm.

For the MID-360, this usually means:

```
Livox LiDAR frame <-> Livox built-in IMU frame
```

This is different from the robot mounting transform:

```
base_link -> livox_frame
```

Do not confuse these two transforms.

FAST-LIO config uses the LiDAR-IMU extrinsic here:

```
~/livox-ws/src/FAST_LIO/config/mid360_go2_nav.yaml
```

Relevant fields:

```
common:
  time_offset_lidar_to_imu: 0.0

mapping:
  extrinsic_est_en: false
  extrinsic_T: [ ... ]
  extrinsic_R: [ ... ]
```

## Recommended safety setup

Before starting calibration:

1. Put the Go2 in a safe state where it will not walk unexpectedly.
2. Keep the robot lifted, on a stand, or in a controlled state if you are going to rotate/pitch/roll it manually.
3. Do not run Nav2 during calibration.
4. Do not run ROS2 Livox driver and ROS1 Livox driver at the same time. They can fight over the same UDP ports.
5. Use a feature-rich area: walls, desks, shelves, boxes, and clear geometric structure.
6. Avoid glass-heavy, empty, hallway-only, or mostly floor-only views.

## Host setup on Ubuntu 22.04 Jetson

Install Docker on the Jetson host:

```
sudo apt update
sudo apt install -y docker.io
sudo usermod -aG docker $USER
newgrp docker
```

Check Docker:

```
docker --version
docker run --rm hello-world
```

If you want RViz or graphical tools from inside the container:

```
xhost +local:docker
```

Create a persistent folder that will be mounted into the container:

```
mkdir -p ~/li_init_docker_ws
mkdir -p ~/li_init_docker_ws/bags
mkdir -p ~/li_init_docker_ws/results
```

## Option A: Build the Docker image with ROS1 Noetic and LI-Init

Create this file on the host:

```
cd ~/li_init_docker_ws
nano Dockerfile
```

Paste this Dockerfile:

```Dockerfile
FROM osrf/ros:noetic-desktop-full

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    cmake \
    wget \
    curl \
    vim \
    nano \
    python3-pip \
    libeigen3-dev \
    libpcl-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libatlas-base-dev \
    libsuitesparse-dev \
    libapr1-dev \
    ros-noetic-pcl-ros \
    ros-noetic-pcl-conversions \
    ros-noetic-tf \
    ros-noetic-tf2-ros \
    ros-noetic-message-filters \
    ros-noetic-cv-bridge \
    ros-noetic-image-transport \
    ros-noetic-rviz \
    ros-noetic-rosbag \
    ros-noetic-diagnostic-updater \
    && rm -rf /var/lib/apt/lists/*

# Build and install Livox-SDK2.
RUN cd /root && \
    git clone https://github.com/Livox-SDK/Livox-SDK2.git && \
    cd Livox-SDK2 && \
    mkdir -p build && \
    cd build && \
    cmake .. && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# Create a ROS1 catkin workspace.
RUN mkdir -p /root/catkin_ws/src

# Build ROS1 livox_ros_driver2. This provides MID-360 support and ROS1 CustomMsg.
RUN cd /root/catkin_ws/src && \
    git clone https://github.com/Livox-SDK/livox_ros_driver2.git && \
    cd /root/catkin_ws/src/livox_ros_driver2 && \
    source /opt/ros/noetic/setup.bash && \
    ./build.sh ROS1

# Build LI-Init.
RUN cd /root/catkin_ws/src && \
    git clone https://github.com/hku-mars/LiDAR_IMU_Init.git && \
    cd /root/catkin_ws && \
    source /opt/ros/noetic/setup.bash && \
    source /root/catkin_ws/devel/setup.bash && \
    catkin_make -j$(nproc)

RUN echo 'source /opt/ros/noetic/setup.bash' >> /root/.bashrc && \
    echo 'source /root/catkin_ws/devel/setup.bash' >> /root/.bashrc && \
    echo 'export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/lib' >> /root/.bashrc

WORKDIR /root/catkin_ws
```

Build the image:

```
cd ~/li_init_docker_ws
docker build -t li-init-noetic-mid360:go2 .
```

The build can take a while on Jetson.

## Start the LI-Init container

Stop any host ROS2 Livox driver first.

Start the container with host networking so it can receive MID-360 UDP packets:

```
docker run -it --rm \
  --name li_init_noetic \
  --network host \
  --ipc host \
  --privileged \
  -e DISPLAY=$DISPLAY \
  -e QT_X11_NO_MITSHM=1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v ~/li_init_docker_ws:/root/li_init_docker_ws \
  li-init-noetic-mid360:go2 \
  bash
```

Inside the container, source the workspace:

```
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/lib
```

## Configure the MID-360 network inside Docker

The container uses `--network host`, so the host network interface must already be able to talk to the MID-360.

On the host or inside the container, check the network interface:

```
ip addr
```

Typical Livox MID-360 config uses a host IP like:

```
192.168.1.5
```

and a LiDAR IP like:

```
192.168.1.12
```

Edit the Livox config inside the container if needed:

```
nano /root/catkin_ws/src/livox_ros_driver2/config/MID360_config.json
```

Make sure the `host_net_info` IPs match the Jetson Ethernet IP, and make sure the LiDAR IP matches the MID-360 IP.

Important field for LI-Init:

```
"pcl_data_type" : 1
```

Use CustomMsg mode for LI-Init/FAST-LIO-style Livox processing.

## Run ROS1 Livox driver inside Docker

In container terminal 1:

```
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
roslaunch livox_ros_driver2 msg_MID360.launch
```

If the launch file name is different in your checkout, list available launch files:

```
ls /root/catkin_ws/src/livox_ros_driver2/launch_ROS1
```

Then run the MID-360 `msg` launch file shown there.

In container terminal 2, verify topics:

```
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
rostopic list
rostopic hz /livox/lidar
rostopic hz /livox/imu
rostopic echo /livox/imu -n 1
```

Expected rates:

- `/livox/lidar`: about 10 Hz
- `/livox/imu`: about 200 Hz

If `/livox/lidar` or `/livox/imu` are missing, fix the Livox driver before running LI-Init.

## Configure LI-Init for MID-360

Check available LI-Init configs and launch files:

```
ls /root/catkin_ws/src/LiDAR_IMU_Init/config
ls /root/catkin_ws/src/LiDAR_IMU_Init/launch
```

If there is already a MID-360 config/launch, use that as the base.

If there is no MID-360 config, copy the Livox Avia config as a starting point:

```
cd /root/catkin_ws/src/LiDAR_IMU_Init
cp config/livox_avia.yaml config/mid360_go2.yaml
cp launch/livox_avia.launch launch/mid360_go2.launch
```

Edit the copied config:

```
nano /root/catkin_ws/src/LiDAR_IMU_Init/config/mid360_go2.yaml
```

Set the important fields. Names can vary slightly between LI-Init versions, so match the exact keys already present in the file.

Use these values as the starting point:

```
lid_topic: /livox/lidar
imu_topic: /livox/imu
orig_odom_freq: 10
cut_frame_num: 5
mean_acc_norm: 1.0
online_refine_time: 20
filter_size_surf: 0.10
filter_size_map: 0.20
```

Notes:

- `cut_frame_num * orig_odom_freq` should be around `50` for Livox sensors.
- `mean_acc_norm` should usually be `1.0` for Livox built-in IMU data in LI-Init, according to the LI-Init README.
- For indoor calibration, `filter_size_surf` around `0.05` to `0.15` is a good range.
- For indoor calibration, `filter_size_map` around `0.15` to `0.25` is a good range.

Edit the copied launch file:

```
nano /root/catkin_ws/src/LiDAR_IMU_Init/launch/mid360_go2.launch
```

Make sure it loads the copied config file:

```
<param name="config_file" value="$(find lidar_imu_init)/config/mid360_go2.yaml" />
```

The exact launch syntax may differ in your LI-Init version. The key goal is that `mid360_go2.launch` loads `mid360_go2.yaml`.

Rebuild after config/launch edits if needed:

```
cd /root/catkin_ws
catkin_make -j$(nproc)
source devel/setup.bash
```

## Run LI-Init live

In container terminal 1, run the Livox driver:

```
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
roslaunch livox_ros_driver2 msg_MID360.launch
```

In container terminal 2, run LI-Init:

```
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
roslaunch lidar_imu_init mid360_go2.launch
```

If your LI-Init package name or launch file differs, check:

```
rospack list | grep -i imu
ls /root/catkin_ws/src/LiDAR_IMU_Init/launch
```

## Calibration motion procedure

LI-Init needs excitation. Do not just drive straight. Do not only yaw in place.

Recommended procedure:

1. Start Livox driver.
2. Start LI-Init.
3. Keep the robot completely still for at least 5 to 10 seconds.
4. Slowly yaw left/right.
5. Slowly pitch the LiDAR/robot nose up/down if physically safe.
6. Slowly roll left/right if physically safe.
7. Translate slowly forward/backward and side-to-side.
8. Repeat the motion for 60 to 120 seconds.
9. Watch LI-Init terminal instructions. It may tell you which direction needs more excitation.
10. Stop when LI-Init reports successful initialization/refinement and writes the result file.

Best practice on a Go2:

- If possible, lift or support the robot and manually excite the sensor rig carefully.
- If the robot is walking, use very slow movement.
- Avoid violent shaking. The motion should be rich, but smooth.
- Keep the LiDAR seeing stable geometry during the whole calibration.

## Record a ROS1 bag during calibration

Recording a bag is strongly recommended. It lets you rerun LI-Init without repeating the robot motion.

In a third container terminal:

```
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
cd /root/li_init_docker_ws/bags
rosbag record /livox/lidar /livox/imu
```

To replay later:

```
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash
roscore
```

In another terminal:

```
rosbag play /root/li_init_docker_ws/bags/YOUR_BAG_NAME.bag --clock
```

Then run LI-Init against the replayed topics:

```
roslaunch lidar_imu_init mid360_go2.launch
```

## Find the calibration result

LI-Init writes the result here:

```
/root/catkin_ws/src/LiDAR_IMU_Init/result/Initialization_result.txt
```

Copy it to the mounted host folder:

```
cp /root/catkin_ws/src/LiDAR_IMU_Init/result/Initialization_result.txt \
   /root/li_init_docker_ws/results/Initialization_result_mid360_go2.txt
```

On the host, it should appear here:

```
~/li_init_docker_ws/results/Initialization_result_mid360_go2.txt
```

Open it and look for:

```
extrinsic_R
extrinsic_T
time offset
```

The exact wording can vary by LI-Init version.

## Copy LI-Init result into ROS2 FAST-LIO

On the ROS2 host/workspace, edit:

```
~/livox-ws/src/FAST_LIO/config/mid360_go2_nav.yaml
```

Update:

```
common:
  time_offset_lidar_to_imu: RESULT_TIME_OFFSET

mapping:
  extrinsic_est_en: false
  extrinsic_T: [ RESULT_TX, RESULT_TY, RESULT_TZ ]
  extrinsic_R: [ R00, R01, R02,
                 R10, R11, R12,
                 R20, R21, R22 ]
```

Then rebuild FAST-LIO:

```
cd ~/livox-ws
colcon build --packages-select fast_lio
source install/setup.bash
```

## Validate FAST-LIO after calibration

Run the ROS2 Livox driver in CustomMsg mode:

```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch livox_ros_driver2 msg_MID360_launch.py
```

Run FAST-LIO:

```
source /opt/ros/humble/setup.bash
source ~/livox-ws/install/setup.bash
ros2 launch fast_lio mapping.launch.py
```

Check odometry while stationary:

```
ros2 topic echo /Odometry --field pose.pose.position
```

Expected result:

- `x`, `y`, and `z` should stay nearly constant while stationary.
- A few centimeters of movement over a minute may be acceptable.
- Tens of centimeters or meters while stationary is not acceptable.

Check pure rotation:

```
ros2 topic echo /Odometry --field pose.pose.position
```

Expected result:

- Yaw changes.
- `x`, `y`, and `z` do not drift heavily.

Only connect FAST-LIO to Nav2 after these two tests pass.

## Common failure cases

### Docker container cannot see the LiDAR

Check:

```
ip addr
ping 192.168.1.12
```

Fixes:

- Use `--network host`.
- Make sure the Jetson Ethernet IP matches `MID360_config.json`.
- Stop the ROS2 Livox driver on the host.
- Check firewall settings.
- Check cable and power.

### Livox driver starts but no `/livox/imu`

Check the Livox config and driver version. MID-360 IMU should be enabled by the driver. If `/livox/imu` is missing, LI-Init cannot calibrate LiDAR-IMU.

### LI-Init does not build because of Livox message type

Some LI-Init versions were originally written against older Livox ROS1 message names, while MID-360 commonly uses `livox_ros_driver2`.

Check the compile error. If it complains about missing `livox_ros_driver/CustomMsg.h`, but your driver provides `livox_ros_driver2/CustomMsg.h`, then the LI-Init source needs a small include/package-name update.

Search inside LI-Init:

```
grep -R "livox_ros_driver" -n /root/catkin_ws/src/LiDAR_IMU_Init
```

Likely replacement for ROS1 livox_ros_driver2:

```
livox_ros_driver/CustomMsg.h  -> livox_ros_driver2/CustomMsg.h
livox_ros_driver::CustomMsg   -> livox_ros_driver2::CustomMsg
```

Also check `package.xml` and `CMakeLists.txt` dependencies. Replace old `livox_ros_driver` dependency with `livox_ros_driver2` if needed.

After edits:

```
cd /root/catkin_ws
catkin_make -j$(nproc)
source devel/setup.bash
```

### LI-Init never converges

Likely causes:

- Not enough roll/pitch/translation excitation.
- Environment has too few geometric features.
- LiDAR mostly sees the floor.
- IMU topic is wrong or unit assumptions are wrong.
- Time offset is too large or unstable.
- The robot is vibrating too much.

Try:

- Move to a more feature-rich area.
- Start with 10 seconds stationary.
- Add slow roll and pitch excitation if safe.
- Record a bag and replay it multiple times while adjusting config.

### Result looks worse in FAST-LIO

Do not assume the first calibration result is correct. Validate with FAST-LIO alone before Nav2.

If FAST-LIO gets worse:

1. Restore the previous `mid360_go2_nav.yaml` values.
2. Try another LI-Init run with better excitation.
3. Compare multiple result files.
4. Only keep results that make stationary and pure-rotation odometry better.

## Minimal success checklist

Before using the calibration in Nav2, all of these should be true:

- ROS1 Docker Livox driver publishes `/livox/lidar` near 10 Hz.
- ROS1 Docker Livox driver publishes `/livox/imu` near 200 Hz.
- LI-Init writes `Initialization_result.txt`.
- FAST-LIO ROS2 runs with the copied extrinsic/time offset.
- `/Odometry` is stable while the Go2 is stationary.
- Pure yaw rotation does not create large fake x/y/z movement.
- Nav2 has only one `/odom` publisher.
- TF chain is `map -> odom -> base_link -> livox_frame`.
