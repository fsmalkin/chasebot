#!/usr/bin/env python3
"""Shared helpers for bounded ball-approach planning."""

from __future__ import annotations

import math
from dataclasses import dataclass

from geometry_msgs.msg import Pose
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import PointStamped


@dataclass(frozen=True)
class RobotPose2D:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class ApproachPlan:
    distance_to_ball_m: float
    goal_distance_local_m: float
    goal_x_local: float
    goal_y_local: float
    goal_x_world: float
    goal_y_world: float
    ball_x_world: float
    ball_y_world: float
    robot_pose: RobotPose2D


def yaw_from_quaternion(q) -> float:
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def pose_to_robot_pose(pose: Pose) -> RobotPose2D:
    return RobotPose2D(
        x=float(pose.position.x),
        y=float(pose.position.y),
        yaw=float(yaw_from_quaternion(pose.orientation)),
    )


def detection_to_local_xy(msg: PointStamped) -> tuple[float, float, float]:
    forward_x = float(msg.point.z)
    left_y = float(-msg.point.x)
    vertical_z = float(msg.point.y)
    return forward_x, left_y, vertical_z


def transform_local_to_world(robot_pose: RobotPose2D, local_x: float, local_y: float) -> tuple[float, float]:
    world_x = robot_pose.x + (math.cos(robot_pose.yaw) * local_x) - (math.sin(robot_pose.yaw) * local_y)
    world_y = robot_pose.y + (math.sin(robot_pose.yaw) * local_x) + (math.cos(robot_pose.yaw) * local_y)
    return world_x, world_y


def plan_approach_from_detection(
    *,
    robot_pose: RobotPose2D,
    detection: PointStamped,
    approach_distance_m: float,
) -> ApproachPlan | None:
    ball_x_local, ball_y_local, _ = detection_to_local_xy(detection)
    distance_to_ball = math.hypot(ball_x_local, ball_y_local)
    if not math.isfinite(distance_to_ball):
        return None
    if distance_to_ball <= max(approach_distance_m, 0.0):
        return None

    unit_x = ball_x_local / distance_to_ball
    unit_y = ball_y_local / distance_to_ball
    goal_distance_local = distance_to_ball - approach_distance_m
    goal_x_local = unit_x * goal_distance_local
    goal_y_local = unit_y * goal_distance_local
    goal_x_world, goal_y_world = transform_local_to_world(robot_pose, goal_x_local, goal_y_local)
    ball_x_world, ball_y_world = transform_local_to_world(robot_pose, ball_x_local, ball_y_local)
    return ApproachPlan(
        distance_to_ball_m=float(distance_to_ball),
        goal_distance_local_m=float(goal_distance_local),
        goal_x_local=float(goal_x_local),
        goal_y_local=float(goal_y_local),
        goal_x_world=float(goal_x_world),
        goal_y_world=float(goal_y_world),
        ball_x_world=float(ball_x_world),
        ball_y_world=float(ball_y_world),
        robot_pose=robot_pose,
    )


def build_goal_pose(*, goal_frame: str, goal_x_world: float, goal_y_world: float, face_x_world: float, face_y_world: float, stamp) -> PoseStamped:
    goal_pose = PoseStamped()
    goal_pose.header.frame_id = goal_frame
    goal_pose.header.stamp = stamp
    goal_pose.pose.position.x = float(goal_x_world)
    goal_pose.pose.position.y = float(goal_y_world)
    goal_pose.pose.position.z = 0.0
    yaw = math.atan2(face_y_world - goal_y_world, face_x_world - goal_x_world)
    goal_pose.pose.orientation.z = math.sin(yaw / 2.0)
    goal_pose.pose.orientation.w = math.cos(yaw / 2.0)
    return goal_pose
