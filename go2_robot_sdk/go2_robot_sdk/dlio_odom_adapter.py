import copy
import math

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


class DlioOdomAdapter(Node):
    """Adapt DLIO odometry into the frame/topic contract Nav2 expects."""

    def __init__(self):
        super().__init__('dlio_odom_adapter')

        self.declare_parameter('input_topic', '/dlio/odom_node/odom')
        self.declare_parameter('output_topic', '/odom')
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('override_frame_ids', True)
        self.declare_parameter('publish_tf', False)
        self.declare_parameter('restamp_with_current_time', False)
        self.declare_parameter('force_2d', True)
        self.declare_parameter('position_deadband', 0.0)
        self.declare_parameter('yaw_deadband', 0.0)
        self.declare_parameter('smoothing_alpha', 1.0)
        self.declare_parameter('max_position_jump', 0.0)
        self.declare_parameter('max_yaw_jump', 0.0)

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
        self.smoothing_alpha = self._clamp(self.get_parameter('smoothing_alpha').value, 0.0, 1.0)
        self.max_position_jump = self.get_parameter('max_position_jump').value
        self.max_yaw_jump = self.get_parameter('max_yaw_jump').value
        self.last_published_odom = None
        self.last_jump_warn_time = None

        self.odom_pub = self.create_publisher(Odometry, self.output_topic, 10)
        self.tf_broadcaster = TransformBroadcaster(self) if self.publish_tf else None
        self.odom_sub = self.create_subscription(
            Odometry,
            self.input_topic,
            self._on_odom,
            10,
        )

        self.get_logger().info(
            f'Adapting DLIO {self.input_topic} -> {self.output_topic} '
            f'({self.odom_frame} -> {self.base_frame}), '
            f'publish_tf={self.publish_tf}, '
            f'restamp_with_current_time={self.restamp_with_current_time}, '
            f'force_2d={self.force_2d}, '
            f'position_deadband={self.position_deadband}, '
            f'yaw_deadband={self.yaw_deadband}, '
            f'smoothing_alpha={self.smoothing_alpha}, '
            f'max_position_jump={self.max_position_jump}, '
            f'max_yaw_jump={self.max_yaw_jump}'
        )

    def _on_odom(self, msg: Odometry) -> None:
        out = copy.deepcopy(msg)

        if self.restamp_with_current_time:
            out.header.stamp = self.get_clock().now().to_msg()

        if self.override_frame_ids:
            out.header.frame_id = self.odom_frame
            out.child_frame_id = self.base_frame

        if self.force_2d:
            self._force_planar_odom(out)

        if self._is_unreasonable_jump(out):
            self._warn_jump_throttled(out)
            return

        if self.last_published_odom is not None:
            if self._inside_deadband(out):
                out.pose.pose = copy.deepcopy(self.last_published_odom.pose.pose)
                self._zero_twist(out)
            elif self.smoothing_alpha < 1.0:
                self._smooth_pose(out)

        self.odom_pub.publish(out)
        self.last_published_odom = copy.deepcopy(out)

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
        distance, yaw_delta = self._delta_from_last(odom)
        return distance < self.position_deadband and yaw_delta < self.yaw_deadband

    def _is_unreasonable_jump(self, odom: Odometry) -> bool:
        if self.last_published_odom is None:
            return False

        distance, yaw_delta = self._delta_from_last(odom)
        position_jump = self.max_position_jump > 0.0 and distance > self.max_position_jump
        yaw_jump = self.max_yaw_jump > 0.0 and yaw_delta > self.max_yaw_jump
        return position_jump or yaw_jump

    def _delta_from_last(self, odom: Odometry) -> tuple[float, float]:
        last = self.last_published_odom.pose.pose
        current = odom.pose.pose
        dx = current.position.x - last.position.x
        dy = current.position.y - last.position.y
        distance = math.hypot(dx, dy)
        yaw_delta = abs(self._normalize_angle(
            self._yaw_from_quaternion(current.orientation)
            - self._yaw_from_quaternion(last.orientation)
        ))
        return distance, yaw_delta

    def _smooth_pose(self, odom: Odometry) -> None:
        alpha = self.smoothing_alpha
        last = self.last_published_odom.pose.pose
        current = odom.pose.pose
        last_yaw = self._yaw_from_quaternion(last.orientation)
        current_yaw = self._yaw_from_quaternion(current.orientation)
        smoothed_yaw = last_yaw + alpha * self._normalize_angle(current_yaw - last_yaw)

        current.position.x = last.position.x + alpha * (current.position.x - last.position.x)
        current.position.y = last.position.y + alpha * (current.position.y - last.position.y)
        current.position.z = 0.0 if self.force_2d else last.position.z + alpha * (current.position.z - last.position.z)
        current.orientation.x = 0.0 if self.force_2d else current.orientation.x
        current.orientation.y = 0.0 if self.force_2d else current.orientation.y
        current.orientation.z = math.sin(smoothed_yaw * 0.5)
        current.orientation.w = math.cos(smoothed_yaw * 0.5)

    @staticmethod
    def _zero_twist(odom: Odometry) -> None:
        odom.twist.twist.linear.x = 0.0
        odom.twist.twist.linear.y = 0.0
        odom.twist.twist.linear.z = 0.0
        odom.twist.twist.angular.x = 0.0
        odom.twist.twist.angular.y = 0.0
        odom.twist.twist.angular.z = 0.0

    def _warn_jump_throttled(self, odom: Odometry) -> None:
        now = self.get_clock().now()
        if self.last_jump_warn_time is not None and (now - self.last_jump_warn_time).nanoseconds < 2_000_000_000:
            return

        distance, yaw_delta = self._delta_from_last(odom)
        self.get_logger().warn(
            f'Ignoring sudden DLIO odom jump: distance={distance:.3f} m, yaw={yaw_delta:.3f} rad'
        )
        self.last_jump_warn_time = now

    @staticmethod
    def _yaw_from_quaternion(q) -> float:
        return math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        )

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        return math.atan2(math.sin(angle), math.cos(angle))

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))


def main(args=None):
    rclpy.init(args=args)
    node = DlioOdomAdapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
