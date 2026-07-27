import math

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


class FastLioOdomAdapter(Node):
    """Adapt FAST-LIO odometry into the frame/topic contract Nav2 expects."""

    def __init__(self):
        super().__init__('fast_lio_odom_adapter')

        self.declare_parameter('input_topic', '/Odometry')
        self.declare_parameter('output_topic', '/odom')
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('override_frame_ids', True)
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('restamp_with_current_time', False)
        self.declare_parameter('force_2d', True)
        self.declare_parameter('position_deadband', 0.01)
        self.declare_parameter('yaw_deadband', 0.01)

        self.input_topic = self.get_parameter('input_topic').value
        self.output_topic = self.get_parameter('output_topic').value
        self.odom_frame = self.get_parameter('odom_frame').value
        self.base_frame = self.get_parameter('base_frame').value
        self.override_frame_ids = self.get_parameter('override_frame_ids').value
        self.publish_tf = self.get_parameter('publish_tf').value
        self.restamp_with_current_time = self.get_parameter('restamp_with_current_time').value
        self.force_2d = self.get_parameter('force_2d').value
        self.position_deadband = self.get_parameter('position_deadband').value
        self.yaw_deadband = self.get_parameter('yaw_deadband').value
        self.last_published_odom = None

        self.odom_pub = self.create_publisher(Odometry, self.output_topic, 10)
        self.tf_broadcaster = TransformBroadcaster(self) if self.publish_tf else None
        self.odom_sub = self.create_subscription(
            Odometry,
            self.input_topic,
            self._on_odom,
            10,
        )

        self.get_logger().info(
            f'Adapting {self.input_topic} -> {self.output_topic} '
            f'({self.odom_frame} -> {self.base_frame}), '
            f'publish_tf={self.publish_tf}, '
            f'restamp_with_current_time={self.restamp_with_current_time}, '
            f'force_2d={self.force_2d}, '
            f'position_deadband={self.position_deadband}, '
            f'yaw_deadband={self.yaw_deadband}'
        )

    def _on_odom(self, msg: Odometry) -> None:
        out = Odometry()
        out.header = msg.header
        out.child_frame_id = msg.child_frame_id
        out.pose = msg.pose
        out.twist = msg.twist

        if self.restamp_with_current_time:
            out.header.stamp = self.get_clock().now().to_msg()

        if self.override_frame_ids:
            out.header.frame_id = self.odom_frame
            out.child_frame_id = self.base_frame

        if self.force_2d:
            self._force_planar_odom(out)

        if self._inside_deadband(out):
            out.pose.pose = self.last_published_odom.pose.pose
            out.twist.twist.linear.x = 0.0
            out.twist.twist.linear.y = 0.0
            out.twist.twist.linear.z = 0.0
            out.twist.twist.angular.x = 0.0
            out.twist.twist.angular.y = 0.0
            out.twist.twist.angular.z = 0.0

        self.odom_pub.publish(out)
        self.last_published_odom = out

        if self.tf_broadcaster is None:
            return

        transform = TransformStamped()
        transform.header.stamp = out.header.stamp
        transform.header.frame_id = out.header.frame_id
        transform.child_frame_id = out.child_frame_id
        transform.transform.translation.x = out.pose.pose.position.x
        transform.transform.translation.y = out.pose.pose.position.y
        transform.transform.translation.z = out.pose.pose.position.z
        transform.transform.rotation = out.pose.pose.orientation
        self.tf_broadcaster.sendTransform(transform)


    def _force_planar_odom(self, odom: Odometry) -> None:
        odom.pose.pose.position.z = 0.0
        yaw = self._yaw_from_quaternion(odom.pose.pose.orientation)
        odom.pose.pose.orientation.x = 0.0
        odom.pose.pose.orientation.y = 0.0
        odom.pose.pose.orientation.z = math.sin(yaw * 0.5)
        odom.pose.pose.orientation.w = math.cos(yaw * 0.5)
        odom.twist.twist.linear.z = 0.0
        odom.twist.twist.angular.x = 0.0
        odom.twist.twist.angular.y = 0.0

    def _inside_deadband(self, odom: Odometry) -> bool:
        if self.last_published_odom is None:
            return False

        last = self.last_published_odom.pose.pose
        current = odom.pose.pose
        dx = current.position.x - last.position.x
        dy = current.position.y - last.position.y
        distance = math.hypot(dx, dy)
        yaw_delta = abs(self._normalize_angle(
            self._yaw_from_quaternion(current.orientation)
            - self._yaw_from_quaternion(last.orientation)
        ))
        return distance < self.position_deadband and yaw_delta < self.yaw_deadband

    @staticmethod
    def _yaw_from_quaternion(q) -> float:
        return math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        )

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        return math.atan2(math.sin(angle), math.cos(angle))


def main(args=None):
    rclpy.init(args=args)
    node = FastLioOdomAdapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
