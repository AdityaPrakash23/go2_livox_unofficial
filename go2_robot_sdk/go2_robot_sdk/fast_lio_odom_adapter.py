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

        self.input_topic = self.get_parameter('input_topic').value
        self.output_topic = self.get_parameter('output_topic').value
        self.odom_frame = self.get_parameter('odom_frame').value
        self.base_frame = self.get_parameter('base_frame').value
        self.override_frame_ids = self.get_parameter('override_frame_ids').value
        self.publish_tf = self.get_parameter('publish_tf').value
        self.restamp_with_current_time = self.get_parameter('restamp_with_current_time').value

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
            f'restamp_with_current_time={self.restamp_with_current_time}'
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

        self.odom_pub.publish(out)

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
