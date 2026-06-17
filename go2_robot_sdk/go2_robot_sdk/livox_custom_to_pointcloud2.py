import math
import struct

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header

from livox_ros_driver2.msg import CustomMsg


class LivoxCustomToPointCloud2(Node):
    """Convert Livox CustomMsg clouds into PointCloud2 for Nav2/AMCL scan input."""

    _POINT_STEP = 16

    def __init__(self):
        super().__init__('livox_custom_to_pointcloud2')

        self.declare_parameter('input_topic', '/livox/lidar')
        self.declare_parameter('output_topic', '/livox/points')
        self.declare_parameter('frame_id', '')
        self.declare_parameter('downsample_rate', 1)
        self.declare_parameter('min_range', 0.0)
        self.declare_parameter('max_range', 0.0)

        self.input_topic = self.get_parameter('input_topic').value
        self.output_topic = self.get_parameter('output_topic').value
        self.frame_id = self.get_parameter('frame_id').value
        self.downsample_rate = max(1, int(self.get_parameter('downsample_rate').value))
        self.min_range = float(self.get_parameter('min_range').value)
        self.max_range = float(self.get_parameter('max_range').value)

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )

        self.publisher = self.create_publisher(PointCloud2, self.output_topic, qos)
        self.subscription = self.create_subscription(
            CustomMsg,
            self.input_topic,
            self._on_cloud,
            qos,
        )

        self.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name='intensity', offset=12, datatype=PointField.FLOAT32, count=1),
        ]

        self.get_logger().info(
            f'Converting {self.input_topic} livox_ros_driver2/CustomMsg '
            f'to {self.output_topic} sensor_msgs/PointCloud2'
        )

    def _on_cloud(self, msg: CustomMsg) -> None:
        data = bytearray()
        min_sq = self.min_range * self.min_range
        max_sq = self.max_range * self.max_range

        for index, point in enumerate(msg.points):
            if index % self.downsample_rate != 0:
                continue

            range_sq = point.x * point.x + point.y * point.y + point.z * point.z
            if self.min_range > 0.0 and range_sq < min_sq:
                continue
            if self.max_range > 0.0 and range_sq > max_sq:
                continue
            if not (math.isfinite(point.x) and math.isfinite(point.y) and math.isfinite(point.z)):
                continue

            data.extend(struct.pack('<ffff', point.x, point.y, point.z, float(point.reflectivity)))

        cloud = PointCloud2()
        cloud.header = Header()
        cloud.header.stamp = msg.header.stamp
        cloud.header.frame_id = self.frame_id or msg.header.frame_id
        cloud.height = 1
        cloud.width = len(data) // self._POINT_STEP
        cloud.fields = self.fields
        cloud.is_bigendian = False
        cloud.point_step = self._POINT_STEP
        cloud.row_step = cloud.point_step * cloud.width
        cloud.data = bytes(data)
        cloud.is_dense = False

        self.publisher.publish(cloud)


def main(args=None):
    rclpy.init(args=args)
    node = LivoxCustomToPointCloud2()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
