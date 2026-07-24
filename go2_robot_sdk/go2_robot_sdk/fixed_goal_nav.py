import math
import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from std_srvs.srv import Trigger


class FixedGoalNavigator(Node):
    """Send, cancel, and restart one fixed Nav2 NavigateToPose goal."""

    def __init__(self):
        super().__init__('fixed_goal_navigator')

        self.declare_parameter('goal_x', 1.0)
        self.declare_parameter('goal_y', 0.0)
        self.declare_parameter('goal_yaw', 0.0)
        self.declare_parameter('goal_frame', 'map')
        self.declare_parameter('navigate_action', 'navigate_to_pose')
        self.declare_parameter('auto_start', True)

        self.goal_handle = None
        self.result_future = None
        self.send_goal_future = None
        self.cancel_future = None

        action_name = self.get_parameter('navigate_action').value
        self.nav_client = ActionClient(self, NavigateToPose, action_name)

        self.create_service(Trigger, '~/stop', self._stop_service)
        self.create_service(Trigger, '~/restart', self._restart_service)

        if self.get_parameter('auto_start').value:
            self.create_timer(0.5, self._start_once)
            self._start_timer_done = False
        else:
            self._start_timer_done = True

        self.get_logger().info(
            f'Ready. Services: {self.get_name()}/stop and '
            f'{self.get_name()}/restart'
        )

    def _start_once(self):
        if self._start_timer_done:
            return
        self._start_timer_done = True
        self.restart_navigation()

    def build_goal_pose(self) -> PoseStamped:
        goal = PoseStamped()
        goal.header.frame_id = self.get_parameter('goal_frame').value
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = float(self.get_parameter('goal_x').value)
        goal.pose.position.y = float(self.get_parameter('goal_y').value)
        goal.pose.position.z = 0.0

        yaw = float(self.get_parameter('goal_yaw').value)
        goal.pose.orientation.z = math.sin(yaw * 0.5)
        goal.pose.orientation.w = math.cos(yaw * 0.5)
        return goal

    def stop_navigation(self) -> tuple[bool, str]:
        """Cancel the current Nav2 task, if one is active."""
        if self.goal_handle is None:
            return False, 'No active navigation goal to cancel'

        if self.cancel_future is not None and not self.cancel_future.done():
            return False, 'Cancel request is already in progress'

        self.cancel_future = self.goal_handle.cancel_goal_async()
        self.cancel_future.add_done_callback(self._on_cancel_done)
        return True, 'Cancel request sent'

    def restart_navigation(self) -> tuple[bool, str]:
        """Cancel any current goal and send the fixed target from the current pose."""
        if not self.nav_client.wait_for_server(timeout_sec=5.0):
            return False, 'Nav2 navigate_to_pose action server is not available'

        if self.goal_handle is not None:
            self.stop_navigation()

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self.build_goal_pose()

        self.get_logger().info(
            'Sending fixed goal: '
            f'x={goal_msg.pose.pose.position.x:.3f}, '
            f'y={goal_msg.pose.pose.position.y:.3f}, '
            f'yaw={self.get_parameter("goal_yaw").value:.3f}, '
            f'frame={goal_msg.pose.header.frame_id}'
        )

        self.send_goal_future = self.nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self._on_feedback,
        )
        self.send_goal_future.add_done_callback(self._on_goal_response)
        return True, 'Navigation goal sent'

    def _stop_service(self, _request, response):
        response.success, response.message = self.stop_navigation()
        return response

    def _restart_service(self, _request, response):
        response.success, response.message = self.restart_navigation()
        return response

    def _on_goal_response(self, future):
        self.goal_handle = future.result()
        if not self.goal_handle.accepted:
            self.goal_handle = None
            self.get_logger().error('Nav2 rejected the fixed goal')
            return

        self.get_logger().info('Nav2 accepted the fixed goal')
        self.result_future = self.goal_handle.get_result_async()
        self.result_future.add_done_callback(self._on_result)

    def _on_feedback(self, feedback_msg):
        feedback = feedback_msg.feedback
        remaining = feedback.distance_remaining
        self.get_logger().info(
            f'Distance remaining: {remaining:.3f} m',
            throttle_duration_sec=2.0,
        )

    def _on_result(self, future):
        status = future.result().status
        status_names = {
            GoalStatus.STATUS_SUCCEEDED: 'succeeded',
            GoalStatus.STATUS_CANCELED: 'canceled',
            GoalStatus.STATUS_ABORTED: 'aborted',
        }
        self.get_logger().info(
            f'Navigation {status_names.get(status, f"finished with status {status}")}'
        )
        self.goal_handle = None
        self.result_future = None

    def _on_cancel_done(self, future):
        cancel_response = future.result()
        if cancel_response.goals_canceling:
            self.get_logger().info('Navigation cancel accepted')
        else:
            self.get_logger().warn('Navigation cancel was not accepted')
        self.cancel_future = None


def main(args=None):
    rclpy.init(args=args)
    node = FixedGoalNavigator()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
