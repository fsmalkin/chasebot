#!/usr/bin/env python3
"""Deterministic gather mission runner for offline/headless corral-and-place proofs."""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_provider_base import ProviderError
from llm_provider_local import LocalModelProvider
from llm_provider_local import LocalStubProvider
from llm_provider_openai import OpenAIResponsesProvider
from llm_supervisor_core import DEFAULT_DASHBOARD_URL
from llm_supervisor_core import DEFAULT_OPENAI_MODEL
from llm_supervisor_core import DEFAULT_REASONING_EFFORT
from llm_supervisor_core import append_jsonl
from llm_supervisor_core import dispatch_intent
from llm_supervisor_core import fetch_dashboard_state
from llm_supervisor_core import http_json
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json
from gather_constrained_local_planner_helpers import CONSTRAINED_LOCAL_PLANNER_CONTROL_FAMILY
from gather_constrained_local_planner_helpers import decide_constrained_local_pre_stage_command
from gather_docking_reacquire_helpers import DOCKING_REACQUIRE_CONTROL_FAMILY
from gather_docking_reacquire_helpers import decide_docking_reacquire_pre_stage_command
from gather_handoff_yaw_servo_helpers import HANDOFF_YAW_SERVO_CONTROL_FAMILY
from gather_handoff_yaw_servo_helpers import decide_handoff_yaw_servo_pre_stage_command
from gather_manager_helpers import GatherManagerState
from gather_manager_helpers import decide_gather_manager_directive
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECENTER_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_KEEPUP_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_KEEPUP_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_KEEPUP_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MAX_CAPTURE_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MIN_LATERAL_TO_ZONE_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_LINE_RECENTER_KEEPUP_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_LINE_RECENTER_MAX_CAPTURE_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_MOVING_LINE_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_MOVING_LINE_RECENTER_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_MOVING_LINE_RECENTER_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_MOVING_LINE_RECENTER_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_POSITIVE_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MIN_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_HIGH_X_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_HIGH_X_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_KEEPUP_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_KEEPUP_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MIN_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WIDE_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WIDE_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WIDE_RECENTER_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_FAR_WORLD_RECENTER_KEEPUP_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_FINISH_KEEPUP_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_FINISH_KEEPUP_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_FINISH_KEEPUP_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_FORWARD_KEEPUP_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_FORWARD_KEEPUP_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_MOTION_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MAX_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MIN_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_EDGE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_EDGE_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MAX_WORLD_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MIN_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MIN_ZONE_MARGIN_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MAX_X_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MIN_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_RECOVERY_RECENTER_MAX_LATERAL_M
from gather_object_centric_policy_helpers import OBJECT_CENTRIC_PLACE_RECOVERY_RECENTER_MAX_X_M
from gather_object_centric_policy_helpers import decide_object_centric_gather_command
from gather_nav2_follow_path_reacquire_helpers import DEFAULT_NAV2_FOLLOW_PATH_BALL_MOTION_TOLERANCE_M
from gather_nav2_follow_path_reacquire_helpers import DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_ID
from gather_nav2_follow_path_reacquire_helpers import DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID
from gather_nav2_follow_path_reacquire_helpers import DEFAULT_NAV2_FOLLOW_PATH_GOAL_TIMEOUT_S
from gather_nav2_follow_path_reacquire_helpers import DEFAULT_NAV2_FOLLOW_PATH_SERVER_WAIT_S
from gather_nav2_follow_path_reacquire_helpers import DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_GOAL_TIMEOUT_S
from gather_nav2_follow_path_reacquire_helpers import NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTROL_FAMILY
from gather_nav2_follow_path_reacquire_helpers import NAV2_FOLLOW_PATH_CORRIDOR_PUSH_OBJECTIVE
from gather_nav2_follow_path_reacquire_helpers import DEFAULT_NAV2_MPPI_FOLLOW_PATH_CONTROLLER_ID
from gather_nav2_follow_path_reacquire_helpers import DEFAULT_NAV2_MPPI_FOLLOW_PATH_GOAL_TIMEOUT_S
from gather_nav2_follow_path_reacquire_helpers import DEFAULT_NAV2_MPPI_FOLLOW_PATH_PRE_STAGE_TIMEOUT_S
from gather_nav2_follow_path_reacquire_helpers import NAV2_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY
from gather_nav2_follow_path_reacquire_helpers import NAV2_FOLLOW_PATH_REACQUIRE_OBJECTIVE
from gather_nav2_follow_path_reacquire_helpers import NAV2_MPPI_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY
from gather_nav2_follow_path_reacquire_helpers import NAV2_MPPI_FOLLOW_PATH_REACQUIRE_OBJECTIVE
from gather_nav2_follow_path_reacquire_helpers import NAV2_FOLLOW_PATH_RESULT_MARKER
from gather_nav2_follow_path_reacquire_helpers import build_nav2_follow_path_corridor_push_plan
from gather_nav2_follow_path_reacquire_helpers import build_nav2_follow_path_reacquire_plan
from gather_nav2_follow_path_reacquire_helpers import build_nav2_mppi_follow_path_reacquire_plan
from gather_pre_stage_reacquire_fsm_helpers import PRE_STAGE_REACQUIRE_FSM_CONTROL_FAMILY
from gather_pre_stage_reacquire_fsm_helpers import decide_pre_stage_reacquire_fsm_command
from gather_pre_stage_path_tracker_helpers import PRE_STAGE_PATH_TRACKER_CONTROL_FAMILY
from gather_pre_stage_path_tracker_helpers import decide_pre_stage_path_tracker_command
from gather_pre_stage_trajectory_owner_helpers import PRE_STAGE_TRAJECTORY_OWNER_CONTROL_FAMILY
from gather_pre_stage_trajectory_owner_helpers import decide_pre_stage_trajectory_owner_command
from gather_region_funnel_helpers import decide_region_funnel_pre_stage_command
from gather_short_horizon_helpers import decide_short_horizon_pre_stage_command
from gather_mission_helpers import DEFAULT_RELEASE_SETTLE_MAX_WAIT_S
from gather_mission_helpers import DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
from gather_mission_helpers import DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
from gather_mission_helpers import DEFAULT_STAGE_READY_DWELL_S
from gather_mission_helpers import CaptureEnvelope
from gather_mission_helpers import GatherTargetSpec
from gather_mission_helpers import PlaceControlCommand
from gather_mission_helpers import approach_side_verdict
from gather_mission_helpers import build_gather_targets
from gather_mission_helpers import build_scorecard_markdown
from gather_mission_helpers import build_zone_spec
from gather_mission_helpers import clamp
from gather_mission_helpers import capture_loss_detected
from gather_mission_helpers import capture_snapshot
from gather_mission_helpers import compute_capture_command
from gather_mission_helpers import compute_place_command
from gather_mission_helpers import compute_pre_stage_command
from gather_mission_helpers import compute_stage_command
from gather_mission_helpers import DEFAULT_PRE_STAGE_READY_DWELL_S
from gather_mission_helpers import DEFAULT_CAPTURE_ENTRY_READY_DWELL_S
from gather_mission_helpers import DEFAULT_CAPTURE_ENTRY_TIMEOUT_S
from gather_mission_helpers import first_contact_push_alignment_deg
from gather_mission_helpers import goal_side_approach_snapshot
from gather_mission_helpers import capture_entry_snapshot
from gather_mission_helpers import compute_capture_entry_command
from gather_mission_helpers import pre_stage_arrival_snapshot
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import pose_delta_m
from gather_mission_helpers import release_ready
from gather_mission_helpers import secure_capture
from gather_mission_helpers import summarize_release_settle_trace
from gather_mission_helpers import world_pose_xyyaw
from gather_mission_helpers import zone_snapshot
from gather_mission_helpers import zone_edge_correction_eligible


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime" / "dashboard"
DEFAULT_GATHER_RUNTIME_STATE_PATH = RUNTIME_DIR / "gather_mission_runtime.json"
DEFAULT_VISIT_RUNTIME_STATE_PATH = RUNTIME_DIR / "visit_mission_runtime.json"
DOCKER_FALLBACK = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
DEFAULT_WORLD_NAME = "yolo_test_world"
DEFAULT_TARGET_MODEL_NAME = "visit_mission_target"
DEFAULT_TARGET_MODEL_SDF = REPO_ROOT / "ros2_config" / "frisbee_target_ball.sdf"
DEFAULT_ZONE_MODEL_NAME = "corral_zone_marker"
DEFAULT_ZONE_MODEL_SDF = REPO_ROOT / "ros2_config" / "corral_zone_marker.sdf"
DEFAULT_MISSION_START_POSE = {"x": 0.0, "y": 0.0, "yaw": 0.0}
DEFAULT_PLACE_RECOVERY_SETTLE_S = 0.20
DEFAULT_PLACE_MARGINAL_CAPTURE_SETTLE_S = 0.25
DEFAULT_OBJECT_CENTRIC_PLACE_TIMEOUT_S = 60.0
DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S = 1.25
DEFAULT_STATIONARY_RECAPTURE_NUDGE_DELAY_S = 1.0
DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S = 0.25
DEFAULT_SETTLE_NO_CHASE_MOTION_TOLERANCE_M = 0.03
DEFAULT_SETTLE_NO_CHASE_ESCAPE_MARGIN_M = 0.08
DEFAULT_SETTLE_NO_CHASE_ESCAPE_TIMEOUT_S = 0.75
DEFAULT_OBJECT_CENTRIC_UNSECURE_SETTLE_ZONE_MAX_M = 0.25
DEFAULT_OBJECT_CENTRIC_UNSECURE_MOVING_SETTLE_ZONE_MAX_M = 0.36
DEFAULT_OBJECT_CENTRIC_UNSECURE_CENTER_ROLLTHROUGH_ZONE_MAX_M = 0.12
DEFAULT_OBJECT_CENTRIC_UNSECURE_CENTER_ROLLTHROUGH_MOTION_MAX_M = 0.045
DEFAULT_OBJECT_CENTRIC_UNSECURE_CENTER_ROLLTHROUGH_MIN_X_M = 1.20
DEFAULT_OBJECT_CENTRIC_UNSECURE_CENTER_ROLLTHROUGH_MAX_LATERAL_M = 0.42
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_ZONE_MAX_M = 0.36
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MOTION_MAX_M = 0.045
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MIN_X_M = 0.80
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MAX_X_M = 1.25
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MIN_LATERAL_M = 0.35
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MAX_LATERAL_M = 1.50
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_ZONE_MAX_M = 0.55
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MOTION_MAX_M = 0.045
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MIN_X_M = 0.65
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MAX_X_M = 0.85
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MIN_LATERAL_M = 0.55
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MAX_LATERAL_M = 0.75
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_ZONE_MAX_M = 0.70
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MOTION_MAX_M = 0.045
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MIN_X_M = 1.40
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MAX_X_M = 1.75
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MIN_LATERAL_M = 0.70
DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MAX_LATERAL_M = 0.95
DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MIN_X_M = -0.45
DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MAX_X_M = 0.10
DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MAX_LATERAL_M = 1.45
DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MIN_WORLD_LATERAL_M = 0.24
DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MAX_WORLD_LATERAL_M = 0.65
DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MAX_MOTION_M = 0.055
DEFAULT_MULTI_BALL_ADVANCE_DWELL_S = 0.5
DEFAULT_MULTI_BALL_ADVANCE_MOTION_TOLERANCE_M = 0.04
DEFAULT_PRE_STAGE_TIMEOUT_S = 30.0
DEFAULT_OBJECT_CENTRIC_PRE_STAGE_TIMEOUT_S = 70.0
DEFAULT_OBJECT_CENTRIC_FETCH_PRE_STAGE_TIMEOUT_S = 90.0
DEFAULT_STAGE_TIMEOUT_S = 6.0
DEFAULT_OBJECT_CENTRIC_STAGE_TIMEOUT_S = 14.0
DEFAULT_OBJECT_CENTRIC_FETCH_CAPTURE_TIMEOUT_S = 32.0
DEFAULT_FETCH_TO_POSE_MIN_LAUNCH_OBSERVE_S = 4.0
DEFAULT_FETCH_TO_POSE_LAUNCH_MOTION_EVIDENCE_M = 0.03
DEFAULT_NAV2_FOLLOW_PATH_FEEDBACK_SAMPLE_MAX = 12
DEFAULT_NAV2_FOLLOW_PATH_FEEDBACK_SAMPLE_INTERVAL_S = 0.5
DEFAULT_NAV2_FOLLOW_PATH_DIAGNOSTIC_SAMPLE_MAX = 20
DEFAULT_NAV2_FOLLOW_PATH_DIAGNOSTIC_SAMPLE_INTERVAL_S = 0.25
DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_LOG_TAIL = 400
MISSION_OBJECTIVE_GATHER_HERE = "gather_here"
MISSION_OBJECTIVE_FETCH_TO_POSE = "fetch_to_pose"
ALLOWED_MISSION_OBJECTIVES = (
    MISSION_OBJECTIVE_GATHER_HERE,
    MISSION_OBJECTIVE_FETCH_TO_POSE,
)
DEFAULT_FETCH_DELIVERY_RADIUS_M = 0.762
ALLOWED_GATHER_CONTROL_FAMILIES = (
    "baseline",
    "short_horizon_v1",
    "short_horizon_v2",
    "region_funnel_v1",
    "nav2_reacquire_v1",
    "constrained_local_planner_v1",
    "docking_reacquire_v1",
    "handoff_yaw_servo_v1",
    "pre_stage_reacquire_fsm_v1",
    "pre_stage_path_tracker_v1",
    "pre_stage_trajectory_owner_v1",
    "nav2_follow_path_reacquire_v1",
    "nav2_mppi_follow_path_reacquire_v1",
    NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTROL_FAMILY,
    "object_centric_gather_policy_v1",
)
NAV2_REACQUIRE_CONTROL_FAMILY = "nav2_reacquire_v1"
DEFAULT_NAV2_REACQUIRE_TRIGGER_DISTANCE_M = 1.20
DEFAULT_NAV2_REACQUIRE_MIN_SEGMENT_BALL_CLEARANCE_M = 0.35
DEFAULT_NAV2_REACQUIRE_MIN_GOAL_BALL_DISTANCE_M = 0.60
DEFAULT_NAV2_REACQUIRE_FALLBACK_FLANK_OFFSET_M = 0.75
DEFAULT_NAV2_REACQUIRE_FALLBACK_BEHIND_BIAS_M = 0.20
DEFAULT_NAV2_REACQUIRE_SERVER_WAIT_S = 5.0
DEFAULT_NAV2_REACQUIRE_GOAL_TIMEOUT_S = 18.0
NAV2_REACQUIRE_RESULT_MARKER = "NAV2_REACQUIRE_RESULT="

_dotenv_path = REPO_ROOT / ".env"
if _dotenv_path.is_file():
    with _dotenv_path.open(encoding="utf-8", errors="ignore") as _handle:
        for _line in _handle:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _value = _line.partition("=")
            _key = _key.strip()
            _value = _value.strip().strip("'\"")
            if _key and _key not in os.environ:
                os.environ[_key] = _value


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def choose_docker_cli() -> str:
    found = shutil.which("docker")
    if found:
        return found
    if DOCKER_FALLBACK.exists():
        return str(DOCKER_FALLBACK)
    raise FileNotFoundError("Unable to locate docker CLI.")


def to_container_repo_path(path: Path) -> str:
    resolved = path.resolve()
    relative = resolved.relative_to(REPO_ROOT.resolve())
    return "/workspaces/chasecar/" + str(relative).replace("\\", "/")


def _segment_distance_m(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    denom = (dx * dx) + (dy * dy)
    if denom <= 1.0e-12:
        return math.hypot(px - sx, py - sy)
    t = max(0.0, min(1.0, (((px - sx) * dx) + ((py - sy) * dy)) / denom))
    closest_x = sx + (t * dx)
    closest_y = sy + (t * dy)
    return math.hypot(px - closest_x, py - closest_y)


def compute_nav2_reacquire_pre_stage_goal(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    pre_stage_snapshot: dict[str, Any],
    *,
    trigger_distance_m: float = DEFAULT_NAV2_REACQUIRE_TRIGGER_DISTANCE_M,
    min_segment_ball_clearance_m: float = DEFAULT_NAV2_REACQUIRE_MIN_SEGMENT_BALL_CLEARANCE_M,
    min_goal_ball_distance_m: float = DEFAULT_NAV2_REACQUIRE_MIN_GOAL_BALL_DISTANCE_M,
    fallback_flank_offset_m: float = DEFAULT_NAV2_REACQUIRE_FALLBACK_FLANK_OFFSET_M,
    fallback_behind_bias_m: float = DEFAULT_NAV2_REACQUIRE_FALLBACK_BEHIND_BIAS_M,
) -> dict[str, Any]:
    """Build the bounded Nav2 waypoint for the experimental pre-stage reacquire slice."""

    robot_xyyaw = world_pose_xyyaw(robot_pose)
    ball_xy = world_pose_xyyaw(ball_pose)
    pre_stage_pose = (
        pre_stage_snapshot.get("pre_stage_pose_world", {})
        if isinstance(pre_stage_snapshot.get("pre_stage_pose_world"), dict)
        else {}
    )
    pre_stage_xy = world_pose_xyyaw(pre_stage_pose)
    if robot_xyyaw is None or ball_xy is None or pre_stage_xy is None:
        return {"active": False, "reason": "missing_reacquire_geometry", "goal_pose": {}}

    pre_stage_pose_reached = bool(pre_stage_snapshot.get("pre_stage_pose_reached", False))
    if pre_stage_pose_reached:
        return {"active": False, "reason": "pre_stage_handoff_already_ready", "goal_pose": {}}

    robot_on_goal_side = bool(pre_stage_snapshot.get("robot_on_goal_side", False))
    pre_stage_distance_m = float(clean_number(pre_stage_snapshot.get("pre_stage_pose_distance_m")) or 0.0)
    if not robot_on_goal_side and pre_stage_distance_m < float(trigger_distance_m):
        return {
            "active": False,
            "reason": "baseline_pre_stage_close_enough",
            "goal_pose": {},
            "trigger": {
                "robot_on_goal_side": False,
                "pre_stage_pose_distance_m": round(pre_stage_distance_m, 6),
            },
        }

    robot_x, robot_y, _robot_yaw = robot_xyyaw
    ball_x, ball_y, _ball_yaw = ball_xy
    goal_x, goal_y, _goal_yaw = pre_stage_xy
    push_direction_yaw_deg = float(clean_number(pre_stage_snapshot.get("push_direction_yaw_deg")) or 0.0)
    push_direction_yaw = math.radians(push_direction_yaw_deg)
    line_ball_clearance_m = _segment_distance_m(
        (ball_x, ball_y),
        (robot_x, robot_y),
        (goal_x, goal_y),
    )
    direct_goal_ball_distance_m = math.hypot(goal_x - ball_x, goal_y - ball_y)
    needs_fallback = bool(
        line_ball_clearance_m < float(min_segment_ball_clearance_m)
        or direct_goal_ball_distance_m < float(min_goal_ball_distance_m)
    )
    goal_kind = "direct_pre_stage"
    if needs_fallback:
        lateral_signed_m = float(clean_number(pre_stage_snapshot.get("robot_lateral_signed_m")) or 0.0)
        flank_sign = -1.0 if lateral_signed_m > 0.0 else 1.0
        if abs(lateral_signed_m) < 1.0e-6 and robot_y < ball_y:
            flank_sign = -1.0
        goal_x = (
            float(pre_stage_xy[0])
            + (flank_sign * float(fallback_flank_offset_m) * -math.sin(push_direction_yaw))
            - (float(fallback_behind_bias_m) * math.cos(push_direction_yaw))
        )
        goal_y = (
            float(pre_stage_xy[1])
            + (flank_sign * float(fallback_flank_offset_m) * math.cos(push_direction_yaw))
            - (float(fallback_behind_bias_m) * math.sin(push_direction_yaw))
        )
        goal_kind = "fallback_flank"

    goal_pose = {
        "frame_id": "odom",
        "x": round(float(goal_x), 6),
        "y": round(float(goal_y), 6),
        "yaw": round(float(push_direction_yaw), 6),
        "yaw_deg": round(float(push_direction_yaw_deg), 6),
        "kind": goal_kind,
    }
    return {
        "active": True,
        "reason": "goal_side_reacquire" if robot_on_goal_side else "far_pre_stage_reacquire",
        "goal_pose": goal_pose,
        "trigger": {
            "robot_on_goal_side": bool(robot_on_goal_side),
            "pre_stage_pose_distance_m": round(pre_stage_distance_m, 6),
            "line_ball_clearance_m": round(float(line_ball_clearance_m), 6),
            "direct_goal_ball_distance_m": round(float(direct_goal_ball_distance_m), 6),
            "fallback_selected": bool(needs_fallback),
        },
    }


def resolve_visit_runtime_state_path(raw_path: str = "") -> Path:
    candidate = str(raw_path or os.environ.get("CHASECAR_VISIT_RUNTIME_PATH") or "").strip()
    if candidate:
        return Path(candidate).resolve()
    return DEFAULT_VISIT_RUNTIME_STATE_PATH.resolve()


def resolve_gather_runtime_state_path(raw_path: str = "") -> Path:
    candidate = str(raw_path or os.environ.get("CHASECAR_GATHER_RUNTIME_PATH") or "").strip()
    if candidate:
        return Path(candidate).resolve()
    return DEFAULT_GATHER_RUNTIME_STATE_PATH.resolve()


def clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def clean_number(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def optional_float_arg(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    numeric = clean_number(value)
    if numeric is None:
        raise argparse.ArgumentTypeError(f"invalid float value: {value!r}")
    return float(numeric)


def clean_rounded_number(value: Any, digits: int = 6) -> float | None:
    numeric = clean_number(value)
    if numeric is None:
        return None
    return round(float(numeric), int(digits))


def pose_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    x_value = clean_number(value.get("x"))
    y_value = clean_number(value.get("y"))
    if x_value is None or y_value is None:
        return {}
    payload: dict[str, Any] = {
        "x": round(float(x_value), 6),
        "y": round(float(y_value), 6),
    }
    z_value = clean_number(value.get("z"))
    yaw_value = clean_number(value.get("yaw"))
    yaw_deg_value = clean_number(value.get("yaw_deg"))
    if z_value is not None:
        payload["z"] = round(float(z_value), 6)
    if yaw_value is not None:
        payload["yaw"] = round(float(yaw_value), 6)
    if yaw_deg_value is not None:
        payload["yaw_deg"] = round(float(yaw_deg_value), 6)
    return payload


def _ball_pose_from_state_row(row: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "ball_pose",
        "final_ball_pose",
        "target_pose_world",
        "target_pose",
    ):
        pose = pose_payload(row.get(key))
        if pose:
            return pose
    belief = row.get("belief", {}) if isinstance(row.get("belief"), dict) else {}
    pose = pose_payload(belief.get("ball_pose"))
    if pose:
        return pose
    target_state = row.get("target", {}) if isinstance(row.get("target"), dict) else {}
    return pose_payload(target_state.get("pose"))


def pose_to_path_distance_m(pose: dict[str, Any] | None, path_pose: dict[str, Any] | None) -> float | None:
    if not isinstance(path_pose, dict):
        return None
    pose_xyyaw = world_pose_xyyaw(pose or {})
    path_x = clean_number(path_pose.get("x"))
    path_y = clean_number(path_pose.get("y"))
    if pose_xyyaw is None or path_x is None or path_y is None:
        return None
    return round(math.hypot(float(path_x) - pose_xyyaw[0], float(path_y) - pose_xyyaw[1]), 6)


def pose_to_path_yaw_error_deg(pose: dict[str, Any] | None, path_pose: dict[str, Any] | None) -> float | None:
    if not isinstance(path_pose, dict):
        return None
    pose_xyyaw = world_pose_xyyaw(pose or {})
    path_yaw = clean_number(path_pose.get("yaw"))
    if pose_xyyaw is None or path_yaw is None:
        return None
    return round(math.degrees(normalize_angle(float(path_yaw) - pose_xyyaw[2])), 6)


def pre_stage_snapshot_number(snapshot: dict[str, Any] | None, key: str) -> float | None:
    if not isinstance(snapshot, dict):
        return None
    return clean_rounded_number(snapshot.get(key))


def numeric_reduction(start: float | None, end: float | None) -> float | None:
    if start is None or end is None:
        return None
    return round(float(start) - float(end), 6)


def default_settle_exit_reason(
    *,
    failure_reason: str = "",
    settled_in_corral_pass: bool = False,
    corrected: bool = False,
    rolled_away_after_release: bool = False,
) -> str:
    if settled_in_corral_pass:
        return "corrected" if corrected else "settled"
    if rolled_away_after_release or str(failure_reason or "").strip() in {"release_roll_away", "capture_lost"}:
        return "rolled_out"
    if str(failure_reason or "").strip() in {"release_unsettled", "place_timeout", "capture_timeout"}:
        return "timeout"
    return ""


def resolve_approach_result_fields(
    *,
    pre_stage_pose_world: dict[str, Any] | None = None,
    pre_stage_pose_reached: bool = False,
    pre_stage_time_s: float = 0.0,
    pre_stage_handoff_pass: bool = False,
    approach_side_verdict: dict[str, Any] | None = None,
    staging_pose_reached: bool = False,
    entered_goal_side_before_capture: bool = False,
    first_contact_push_alignment_deg: float | None = None,
    push_direction_yaw_deg: float = 0.0,
    stage_time_s: float = 0.0,
    capture_entry_reached: bool = False,
    capture_entry_time_s: float = 0.0,
    approach_failure_reason: str = "",
    latest_approach_progress: dict[str, Any] | None = None,
    fresh_attempt_approach: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = {
        "pre_stage_pose_world": pre_stage_pose_world if isinstance(pre_stage_pose_world, dict) else {},
        "pre_stage_pose_reached": bool(pre_stage_pose_reached),
        "pre_stage_time_s": float(clean_number(pre_stage_time_s) or 0.0),
        "pre_stage_handoff_pass": bool(pre_stage_handoff_pass),
        "approach_side_verdict": approach_side_verdict if isinstance(approach_side_verdict, dict) else {},
        "staging_pose_reached": bool(staging_pose_reached),
        "entered_goal_side_before_capture": bool(entered_goal_side_before_capture),
        "first_contact_push_alignment_deg": clean_number(first_contact_push_alignment_deg),
        "push_direction_yaw_deg": float(clean_number(push_direction_yaw_deg) or 0.0),
        "stage_time_s": float(clean_number(stage_time_s) or 0.0),
        "capture_entry_reached": bool(capture_entry_reached),
        "capture_entry_time_s": float(clean_number(capture_entry_time_s) or 0.0),
        "approach_failure_reason": clean_text(approach_failure_reason),
    }

    def _apply_structured_approach_progress(progress: dict[str, Any]) -> None:
        pre_stage = progress.get("pre_stage", {}) if isinstance(progress.get("pre_stage"), dict) else {}
        stage = progress.get("stage", {}) if isinstance(progress.get("stage"), dict) else {}
        capture_entry = progress.get("capture_entry", {}) if isinstance(progress.get("capture_entry"), dict) else {}
        progress_pre_stage_pose_world = (
            pre_stage.get("pose_world", {})
            if isinstance(pre_stage.get("pose_world"), dict)
            else {}
        )
        if progress_pre_stage_pose_world:
            resolved["pre_stage_pose_world"] = dict(progress_pre_stage_pose_world)
        resolved["pre_stage_pose_reached"] = bool(pre_stage.get("pose_reached", resolved["pre_stage_pose_reached"]))
        pre_stage_time_value = clean_number(pre_stage.get("time_s"))
        if pre_stage_time_value is not None:
            resolved["pre_stage_time_s"] = float(pre_stage_time_value)
        resolved["pre_stage_handoff_pass"] = bool(pre_stage.get("handoff_pass", resolved["pre_stage_handoff_pass"]))
        resolved["approach_side_verdict"] = {
            "pass": bool(progress.get("pass", False)),
            "reason": clean_text(progress.get("reason")),
        }
        resolved["staging_pose_reached"] = bool(stage.get("pose_reached", resolved["staging_pose_reached"]))
        stage_time_value = clean_number(stage.get("time_s"))
        if stage_time_value is not None:
            resolved["stage_time_s"] = float(stage_time_value)
        resolved["entered_goal_side_before_capture"] = bool(
            capture_entry.get("entered_goal_side_before_capture", resolved["entered_goal_side_before_capture"])
        )
        if "first_contact_push_alignment_deg" in capture_entry:
            resolved["first_contact_push_alignment_deg"] = clean_number(capture_entry.get("first_contact_push_alignment_deg"))
        capture_entry_time_value = clean_number(capture_entry.get("time_s"))
        capture_entry_failure_reason = clean_text(capture_entry.get("failure_reason"))
        capture_entry_reached_progress = bool(
            capture_entry.get(
                "reached",
                capture_entry.get("pass", resolved["capture_entry_reached"]),
            )
        )
        resolved["capture_entry_reached"] = capture_entry_reached_progress
        if capture_entry_time_value is not None:
            resolved["capture_entry_time_s"] = float(capture_entry_time_value)
        if "push_direction_yaw_deg" in capture_entry:
            resolved["push_direction_yaw_deg"] = float(clean_number(capture_entry.get("push_direction_yaw_deg")) or 0.0)
        resolved["approach_failure_reason"] = clean_text(
            capture_entry_failure_reason,
            clean_text(progress.get("reason")),
        )

    latest = latest_approach_progress if isinstance(latest_approach_progress, dict) else {}
    if latest:
        _apply_structured_approach_progress(latest)
        return resolved
    return resolved


def truth_world_xy(pose: dict[str, Any]) -> dict[str, float] | None:
    position = pose.get("position") if isinstance(pose.get("position"), dict) else {}
    x = clean_number(position.get("x"))
    y = clean_number(position.get("y"))
    z = clean_number(position.get("z"))
    if x is None or y is None:
        return None
    payload = {"x": round(float(x), 6), "y": round(float(y), 6)}
    if z is not None:
        payload["z"] = round(float(z), 6)
    return payload


def build_provider(provider_name: str, *, model: str, reasoning_effort: str):
    normalized = str(provider_name or "").strip().lower() or "openai"
    if normalized == "openai":
        return OpenAIResponsesProvider(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=model,
            reasoning_effort=reasoning_effort,
            base_url=os.environ.get("OPENAI_BASE_URL", ""),
            org_id=os.environ.get("OPENAI_ORG_ID", ""),
            project_id=os.environ.get("OPENAI_PROJECT_ID", ""),
        )
    if normalized == "local_stub":
        return LocalStubProvider(model=model or "local-stub")
    if normalized == "local_model":
        return LocalModelProvider(model=model or "local-model")
    raise ValueError(f"Unsupported provider: {provider_name}")


def _load_target_layout_override(raw_value: str) -> list[GatherTargetSpec]:
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return []
    candidate_path = Path(raw_text)
    if candidate_path.is_file():
        payload = read_json(candidate_path)
    else:
        payload = json.loads(raw_text)
    items = payload.get("targets", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not items:
        raise ValueError("Target layout override must provide a non-empty target list.")
    targets: list[GatherTargetSpec] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError("Each target override entry must be an object.")
        target_id = clean_text(item.get("id"), f"ball_{index}")
        label = clean_text(item.get("label"), target_id)
        forward_m = clean_number(item.get("forward_m"))
        lateral_m = clean_number(item.get("lateral_m"))
        if forward_m is None or lateral_m is None:
            raise ValueError(f"Target override {target_id} requires numeric forward_m and lateral_m.")
        targets.append(
            GatherTargetSpec(
                id=target_id,
                label=label,
                start_visible=bool(item.get("start_visible", False)),
                forward_m=float(forward_m),
                lateral_m=float(lateral_m),
                z_m=float(clean_number(item.get("z_m")) or 0.05),
                visit_tolerance_m=float(clean_number(item.get("visit_tolerance_m")) or 0.35),
                min_dwell_s=float(clean_number(item.get("min_dwell_s")) or 1.0),
            )
        )
    return targets


class GatherMissionRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.dashboard_url = args.dashboard_url.rstrip("/")
        self.targets = _load_target_layout_override(getattr(args, "target_layout_json", "")) or build_gather_targets(args.scenario_id)
        self.targets_by_id = {item.id: item for item in self.targets}
        self.zone = build_zone_spec(args.scenario_id)
        self.capture_envelope = CaptureEnvelope()
        self.docker = choose_docker_cli()
        self.world_file = clean_text(args.world_file)
        self.surface_profile = clean_text(args.surface_profile, "baseline")
        self.gather_control_family = clean_text(getattr(args, "gather_control_family", "baseline"), "baseline").lower()
        if self.gather_control_family not in ALLOWED_GATHER_CONTROL_FAMILIES:
            self.gather_control_family = "baseline"
        self.mission_objective = clean_text(
            getattr(args, "mission_objective", MISSION_OBJECTIVE_GATHER_HERE),
            MISSION_OBJECTIVE_GATHER_HERE,
        ).lower()
        if self.mission_objective not in ALLOWED_MISSION_OBJECTIVES:
            self.mission_objective = MISSION_OBJECTIVE_GATHER_HERE
        self.fetch_delivery_radius_m = max(
            0.05,
            float(clean_number(getattr(args, "fetch_delivery_radius_m", DEFAULT_FETCH_DELIVERY_RADIUS_M)) or DEFAULT_FETCH_DELIVERY_RADIUS_M),
        )
        self.visit_runtime_state_path = resolve_visit_runtime_state_path(args.visit_runtime_json)
        self.gather_runtime_state_path = resolve_gather_runtime_state_path(args.gather_runtime_json)
        self.visit_runtime_state: dict[str, Any] = {}
        self.gather_runtime_state: dict[str, Any] = {}
        self._gather_sequence = 0
        self.provider = build_provider(
            args.provider,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        self._event_keys: set[str] = set()
        self._started_here = False

    def _control_debug_fields(
        self,
        *,
        strategy_name: str = "",
        objective_name: str = "",
        progress_score: float | None = None,
        stall_s: float | None = None,
        projected_projection_gain: float | None = None,
        projected_lateral_gain: float | None = None,
        projected_distance_gain: float | None = None,
    ) -> dict[str, Any]:
        return {
            "controller_family": self.gather_control_family,
            "strategy_name": clean_text(strategy_name),
            "objective_name": clean_text(objective_name),
            "progress_score": round(float(progress_score), 6) if progress_score is not None else None,
            "stall_s": round(float(stall_s), 6) if stall_s is not None else None,
            "projected_projection_gain": (
                round(float(projected_projection_gain), 6)
                if projected_projection_gain is not None
                else None
            ),
            "projected_lateral_gain": (
                round(float(projected_lateral_gain), 6)
                if projected_lateral_gain is not None
                else None
            ),
            "projected_distance_gain": (
                round(float(projected_distance_gain), 6)
                if projected_distance_gain is not None
                else None
            ),
        }

    def _fetch_pose_world(self) -> dict[str, Any]:
        configured_x = clean_number(getattr(self.args, "fetch_target_x", None))
        configured_y = clean_number(getattr(self.args, "fetch_target_y", None))
        configured_z = clean_number(getattr(self.args, "fetch_target_z", None))
        fetch_x = float(configured_x) if configured_x is not None else float(self.zone.world_x)
        fetch_y = float(configured_y) if configured_y is not None else float(self.zone.world_y)
        fetch_z = float(configured_z) if configured_z is not None else float(self.zone.z_m)
        return {
            "x": round(fetch_x, 6),
            "y": round(fetch_y, 6),
            "z": round(fetch_z, 6),
            "radius_m": round(float(self.fetch_delivery_radius_m), 6),
        }

    def _state_history_ball_samples(
        self,
        *,
        state_history_path: Path,
        target_id: str,
        phase: str | None = None,
    ) -> list[dict[str, Any]]:
        if not state_history_path.exists():
            return []
        samples: list[dict[str, Any]] = []
        with state_history_path.open(encoding="utf-8", errors="ignore") as handle:
            for line_index, raw_line in enumerate(handle):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    row = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                row_target_id = clean_text(row.get("target_id"))
                if row_target_id and row_target_id != target_id:
                    continue
                row_phase = clean_text(row.get("phase"))
                if phase is not None and row_phase != phase:
                    continue
                ball_pose = _ball_pose_from_state_row(row)
                if not ball_pose:
                    continue
                samples.append(
                    {
                        "line_index": line_index,
                        "generated_utc": clean_text(row.get("generated_utc")),
                        "event_type": clean_text(row.get("event_type")),
                        "phase": row_phase,
                        "ball_pose": ball_pose,
                    }
                )
        return samples

    def _build_fetch_to_pose_outcome(
        self,
        *,
        target: GatherTargetSpec,
        state_history_path: Path,
        final_ball_pose: dict[str, Any] | None,
        place_payload: dict[str, Any] | None,
        place_failure_reason: str = "",
    ) -> dict[str, Any]:
        fetch_pose = self._fetch_pose_world()
        fetch_xy = world_pose_xyyaw(fetch_pose)
        samples = self._state_history_ball_samples(
            state_history_path=state_history_path,
            target_id=target.id,
            phase="fetch_to_pose",
        )
        final_pose_payload = pose_payload(final_ball_pose or {})
        if final_pose_payload:
            samples.append(
                {
                    "line_index": -1,
                    "generated_utc": utc_now(),
                    "event_type": "fetch_to_pose_final_pose",
                    "phase": "fetch_to_pose",
                    "ball_pose": final_pose_payload,
                }
            )
        if fetch_xy is None:
            return {
                "observed": bool(samples),
                "pass": False,
                "reason": "missing_fetch_pose",
                "fetch_pose_world": fetch_pose,
                "delivery_radius_m": round(float(self.fetch_delivery_radius_m), 6),
                "sample_count": len(samples),
                "ball_start_pose": {},
                "ball_end_pose": final_pose_payload,
                "distance_to_fetch_pose_m": None,
                "closest_approach_distance_m": None,
                "closest_pose": {},
                "surface_profile": self.surface_profile,
            }

        radius_m = max(float(self.fetch_delivery_radius_m), 0.0)
        closest_distance: float | None = None
        closest_pose: dict[str, Any] = {}
        previous_xy: tuple[float, float] | None = None
        previous_pose: dict[str, Any] = {}
        fetch_point = (float(fetch_xy[0]), float(fetch_xy[1]))
        for sample in samples:
            pose = pose_payload(sample.get("ball_pose"))
            pose_xyyaw = world_pose_xyyaw(pose)
            if pose_xyyaw is None:
                continue
            current_xy = (float(pose_xyyaw[0]), float(pose_xyyaw[1]))
            point_distance = math.hypot(current_xy[0] - fetch_point[0], current_xy[1] - fetch_point[1])
            if closest_distance is None or point_distance < closest_distance:
                closest_distance = point_distance
                closest_pose = dict(pose)
            if previous_xy is not None:
                segment_distance = _segment_distance_m(fetch_point, previous_xy, current_xy)
                if closest_distance is None or segment_distance < closest_distance:
                    closest_distance = segment_distance
                    closest_pose = dict(pose if point_distance <= math.hypot(previous_xy[0] - fetch_point[0], previous_xy[1] - fetch_point[1]) else previous_pose)
            previous_xy = current_xy
            previous_pose = dict(pose)

        observed = closest_distance is not None
        pass_delivery = bool(observed and closest_distance is not None and closest_distance <= radius_m)
        ball_start_pose = dict(samples[0]["ball_pose"]) if samples else {}
        ball_end_pose = dict(samples[-1]["ball_pose"]) if samples else {}
        end_xyyaw = world_pose_xyyaw(ball_end_pose)
        distance_to_fetch_pose_m = (
            math.hypot(float(end_xyyaw[0]) - fetch_point[0], float(end_xyyaw[1]) - fetch_point[1])
            if end_xyyaw is not None
            else None
        )
        zone_score = zone_snapshot(ball_end_pose, self.zone) if ball_end_pose else None
        settle_metrics = (
            place_payload.get("settle_metrics", {})
            if isinstance(place_payload, dict) and isinstance(place_payload.get("settle_metrics"), dict)
            else {}
        )
        fetch_phase_metrics = {}
        if isinstance(place_payload, dict):
            for key in (
                "fetch_observe_count",
                "fetch_elapsed_s",
                "fetch_still_s",
                "fetch_ball_displacement_m",
                "fetch_ball_moved_since_fetch",
                "fetch_min_launch_observe_s",
                "fetch_launch_motion_evidence_m",
                "fetch_max_commanded_linear_x_mps",
                "fetch_max_target_speed_scale",
            ):
                if key in place_payload:
                    fetch_phase_metrics[key] = place_payload.get(key)
        if pass_delivery:
            reason = "trajectory_intersects_delivery_radius"
        elif not observed:
            reason = "no_ball_samples"
        else:
            reason = "missed_delivery_radius"
            if place_failure_reason:
                reason = f"{reason}_after_{place_failure_reason}"
        return {
            "observed": bool(observed),
            "pass": bool(pass_delivery),
            "reason": reason,
            "fetch_pose_world": fetch_pose,
            "delivery_radius_m": round(float(radius_m), 6),
            "sample_count": len(samples),
            "ball_start_pose": ball_start_pose,
            "ball_end_pose": ball_end_pose,
            "distance_to_fetch_pose_m": (
                round(float(distance_to_fetch_pose_m), 6)
                if distance_to_fetch_pose_m is not None
                else None
            ),
            "closest_approach_distance_m": (
                round(float(closest_distance), 6)
                if closest_distance is not None
                else None
            ),
            "closest_pose": closest_pose,
            "distance_to_zone_m": (
                round(float(zone_score.retrieval_distance_m), 6)
                if zone_score is not None
                else None
            ),
            "inside_retrieval_corral": bool(zone_score.center_inside_retrieval_corral) if zone_score is not None else False,
            "ball_stopped": bool(settle_metrics.get("ball_stopped_in_corral", False)),
            "rolled_away": bool(
                settle_metrics.get(
                    "rolled_away_after_release",
                    place_payload.get("rolled_away_after_release", False) if isinstance(place_payload, dict) else False,
                )
            ),
            "max_overshoot_distance_m": round(float(clean_number(settle_metrics.get("max_overshoot_distance_m")) or 0.0), 6),
            "surface_profile": self.surface_profile,
            **fetch_phase_metrics,
        }

    def _persist_visit_runtime_state(self) -> None:
        write_json(self.visit_runtime_state_path, self.visit_runtime_state)

    def _persist_gather_runtime_state(self) -> None:
        write_json(self.gather_runtime_state_path, self.gather_runtime_state)

    def _update_visit_runtime_state(self, **updates: Any) -> None:
        self.visit_runtime_state.update(updates)
        self.visit_runtime_state["updated_utc"] = utc_now()
        self._persist_visit_runtime_state()

    def _update_gather_runtime_state(self, **updates: Any) -> None:
        self.gather_runtime_state.update(updates)
        self.gather_runtime_state["updated_utc"] = utc_now()
        self._persist_gather_runtime_state()

    def _append_runtime_event(self, message: str, *, category: str = "mission", key: str = "") -> None:
        event_key = key or message
        if event_key in self._event_keys:
            return
        self._event_keys.add(event_key)
        event = {
            "timestamp_utc": utc_now(),
            "message": str(message),
            "category": str(category),
            "source": "gather_mission",
        }
        for state, persist in (
            (self.visit_runtime_state, self._persist_visit_runtime_state),
            (self.gather_runtime_state, self._persist_gather_runtime_state),
        ):
            events = list(state.get("recent_operator_events", []))
            events.append(event)
            state["recent_operator_events"] = events[-30:]
            state["latest_operator_event"] = event["message"]
            state["updated_utc"] = event["timestamp_utc"]
            persist()

    def _target_failure_result(
        self,
        *,
        target: GatherTargetSpec,
        failure_reason: str,
        failure_stage: str,
        attempts: int,
        capture_loss_count: int,
        route_index: int,
        attempt_kind: str,
        local_recovery_attempted: bool = False,
        revisit_attempted: bool = False,
        settle_metrics: dict[str, Any] | None = None,
        stopped_with_ball_captured: bool = False,
        release_started_with_capture: bool = False,
        stop_capture_state: dict[str, Any] | None = None,
        release_capture_state: dict[str, Any] | None = None,
        clean_retention_pass: bool = False,
        final_inside_retrieval_corral: bool = False,
        final_center_inside_zone: bool = False,
        ball_stopped_in_corral: bool = False,
        rolled_away_after_release: bool = False,
        settled_in_corral_pass: bool = False,
        practical_retrieval_pass: bool = False,
        handoff_kind: str = "",
        zone_edge_correction_count: int = 0,
        place_controller_reentry_count: int = 0,
        post_visit_revisit_count: int = 0,
        settle_exit_reason: str = "",
        settle_no_chase_activated: bool = False,
        settle_no_chase_exit_reason: str = "none",
        release_gate_blocked_reason: str = "none",
        pre_stage_pose_world: dict[str, Any] | None = None,
        pre_stage_pose_reached: bool = False,
        pre_stage_time_s: float = 0.0,
        pre_stage_handoff_pass: bool = False,
        approach_side_verdict: dict[str, Any] | None = None,
        staging_pose_reached: bool = False,
        entered_goal_side_before_capture: bool = False,
        first_contact_push_alignment_deg: float | None = None,
        push_direction_yaw_deg: float = 0.0,
        stage_time_s: float = 0.0,
        capture_entry_reached: bool = False,
        capture_entry_time_s: float = 0.0,
        approach_failure_reason: str = "",
        latest_approach_progress: dict[str, Any] | None = None,
        fresh_attempt_approach: dict[str, Any] | None = None,
        fetch_to_pose_reached: bool = False,
        fetch_to_pose_time_s: float = 0.0,
        fetch_to_pose_failure_reason: str = "",
        fetch_pose_world: dict[str, Any] | None = None,
        shot_outcome: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        approach_fields = resolve_approach_result_fields(
            pre_stage_pose_world=pre_stage_pose_world,
            pre_stage_pose_reached=pre_stage_pose_reached,
            pre_stage_time_s=pre_stage_time_s,
            pre_stage_handoff_pass=pre_stage_handoff_pass,
            approach_side_verdict=approach_side_verdict,
            staging_pose_reached=staging_pose_reached,
            entered_goal_side_before_capture=entered_goal_side_before_capture,
            first_contact_push_alignment_deg=first_contact_push_alignment_deg,
            push_direction_yaw_deg=push_direction_yaw_deg,
            stage_time_s=stage_time_s,
            capture_entry_reached=capture_entry_reached,
            capture_entry_time_s=capture_entry_time_s,
            approach_failure_reason=approach_failure_reason,
            latest_approach_progress=latest_approach_progress,
            fresh_attempt_approach=fresh_attempt_approach,
        )
        resolved_settle_exit_reason = clean_text(
            settle_exit_reason,
            default_settle_exit_reason(
                failure_reason=str(failure_reason),
                settled_in_corral_pass=bool(settled_in_corral_pass),
                corrected=bool(zone_edge_correction_count or place_controller_reentry_count),
                rolled_away_after_release=bool(rolled_away_after_release),
            ),
        )
        payload = {
            "target_id": target.id,
            "label": target.label,
            "pass": False,
            "mission_objective": self.mission_objective,
            "failure_reason": str(failure_reason),
            "failure_stage": str(failure_stage),
            "attempts": int(attempts),
            "attempt_kind": str(attempt_kind),
            "capture_loss_count": int(capture_loss_count),
            "route_index": int(route_index),
            "local_recovery_attempted": bool(local_recovery_attempted),
            "revisit_attempted": bool(revisit_attempted),
            "surface_profile": self.surface_profile,
            "fetched": bool(fetch_to_pose_reached),
            "fetch_to_pose_reached": bool(fetch_to_pose_reached),
            "fetch_to_pose_time_s": round(float(fetch_to_pose_time_s), 6),
            "fetch_to_pose_failure_reason": clean_text(fetch_to_pose_failure_reason, clean_text(failure_reason)),
            "fetch_pose_world": dict(fetch_pose_world) if isinstance(fetch_pose_world, dict) else {},
            "fetch_delivery_radius_m": round(float(self.fetch_delivery_radius_m), 6),
            "shot_outcome": dict(shot_outcome) if isinstance(shot_outcome, dict) else {},
            "handoff_kind": clean_text(handoff_kind, "unspecified"),
            "zone_edge_correction_count": int(zone_edge_correction_count),
            "place_controller_reentry_count": int(place_controller_reentry_count),
            "post_visit_revisit_count": int(post_visit_revisit_count),
            "stopped_with_ball_captured": bool(stopped_with_ball_captured),
            "release_started_with_capture": bool(release_started_with_capture),
            "stop_capture_state": stop_capture_state if isinstance(stop_capture_state, dict) else {},
            "release_capture_state": release_capture_state if isinstance(release_capture_state, dict) else {},
            "clean_retention_pass": bool(clean_retention_pass),
            "final_inside_retrieval_corral": bool(final_inside_retrieval_corral),
            "final_center_inside_zone": bool(final_center_inside_zone),
            "ball_stopped_in_corral": bool(ball_stopped_in_corral),
            "rolled_away_after_release": bool(rolled_away_after_release),
            "settled_in_corral_pass": bool(settled_in_corral_pass),
            "practical_retrieval_pass": bool(practical_retrieval_pass),
            "settle_exit_reason": resolved_settle_exit_reason,
            "settle_no_chase_activated": bool(settle_no_chase_activated),
            "settle_no_chase_exit_reason": clean_text(settle_no_chase_exit_reason, "none"),
            "release_gate_blocked_reason": clean_text(release_gate_blocked_reason, "none"),
            "pre_stage_pose_world": dict(approach_fields["pre_stage_pose_world"]),
            "pre_stage_pose_reached": bool(approach_fields["pre_stage_pose_reached"]),
            "pre_stage_time_s": round(float(approach_fields["pre_stage_time_s"]), 6),
            "pre_stage_handoff_pass": bool(approach_fields["pre_stage_handoff_pass"]),
            "approach_side_verdict": dict(approach_fields["approach_side_verdict"]),
            "staging_pose_reached": bool(approach_fields["staging_pose_reached"]),
            "entered_goal_side_before_capture": bool(approach_fields["entered_goal_side_before_capture"]),
            "first_contact_push_alignment_deg": clean_number(approach_fields["first_contact_push_alignment_deg"]),
            "push_direction_yaw_deg": round(float(approach_fields["push_direction_yaw_deg"]), 6),
            "stage_time_s": round(float(approach_fields["stage_time_s"]), 6),
            "capture_entry_reached": bool(approach_fields["capture_entry_reached"]),
            "capture_entry_time_s": round(float(approach_fields["capture_entry_time_s"]), 6),
            "approach_failure_reason": clean_text(approach_fields["approach_failure_reason"]),
            "latest_approach_progress": (
                dict(latest_approach_progress)
                if isinstance(latest_approach_progress, dict)
                else {}
            ),
            "fresh_attempt_approach": (
                dict(fresh_attempt_approach)
                if isinstance(fresh_attempt_approach, dict)
                else {}
            ),
        }
        if isinstance(settle_metrics, dict):
            payload.update(settle_metrics)
            payload["settle_exit_reason"] = clean_text(payload.get("settle_exit_reason"), resolved_settle_exit_reason)
        return payload

    def _target_success_result(
        self,
        *,
        target: GatherTargetSpec,
        attempts: int,
        capture_loss_count: int,
        route_index: int,
        final_ball_pose: dict[str, Any],
        place_time_s: float,
        attempt_kind: str,
        local_recovery_attempted: bool = False,
        revisit_attempted: bool = False,
        settle_metrics: dict[str, Any] | None = None,
        stopped_with_ball_captured: bool = False,
        release_started_with_capture: bool = False,
        stop_capture_state: dict[str, Any] | None = None,
        release_capture_state: dict[str, Any] | None = None,
        clean_retention_pass: bool | None = None,
        final_inside_retrieval_corral: bool = False,
        final_center_inside_zone: bool = False,
        ball_stopped_in_corral: bool = False,
        rolled_away_after_release: bool = False,
        settled_in_corral_pass: bool | None = None,
        practical_retrieval_pass: bool | None = None,
        handoff_kind: str = "",
        zone_edge_correction_count: int = 0,
        place_controller_reentry_count: int = 0,
        post_visit_revisit_count: int = 0,
        settle_exit_reason: str = "",
        settle_no_chase_activated: bool = False,
        settle_no_chase_exit_reason: str = "none",
        release_gate_blocked_reason: str = "none",
        pre_stage_pose_world: dict[str, Any] | None = None,
        pre_stage_pose_reached: bool = False,
        pre_stage_time_s: float = 0.0,
        pre_stage_handoff_pass: bool = False,
        approach_side_verdict: dict[str, Any] | None = None,
        staging_pose_reached: bool = False,
        entered_goal_side_before_capture: bool = False,
        first_contact_push_alignment_deg: float | None = None,
        push_direction_yaw_deg: float = 0.0,
        stage_time_s: float = 0.0,
        capture_entry_reached: bool = False,
        capture_entry_time_s: float = 0.0,
        approach_failure_reason: str = "",
        latest_approach_progress: dict[str, Any] | None = None,
        fresh_attempt_approach: dict[str, Any] | None = None,
        fetch_to_pose_reached: bool = False,
        fetch_to_pose_time_s: float = 0.0,
        fetch_to_pose_failure_reason: str = "",
        fetch_pose_world: dict[str, Any] | None = None,
        shot_outcome: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        approach_fields = resolve_approach_result_fields(
            pre_stage_pose_world=pre_stage_pose_world,
            pre_stage_pose_reached=pre_stage_pose_reached,
            pre_stage_time_s=pre_stage_time_s,
            pre_stage_handoff_pass=pre_stage_handoff_pass,
            approach_side_verdict=approach_side_verdict,
            staging_pose_reached=staging_pose_reached,
            entered_goal_side_before_capture=entered_goal_side_before_capture,
            first_contact_push_alignment_deg=first_contact_push_alignment_deg,
            push_direction_yaw_deg=push_direction_yaw_deg,
            stage_time_s=stage_time_s,
            capture_entry_reached=capture_entry_reached,
            capture_entry_time_s=capture_entry_time_s,
            approach_failure_reason=approach_failure_reason,
            latest_approach_progress=latest_approach_progress,
            fresh_attempt_approach=fresh_attempt_approach,
        )
        settle_payload = settle_metrics if isinstance(settle_metrics, dict) else {}
        final_inside_retrieval_corral = bool(settle_payload.get("final_inside_retrieval_corral", final_inside_retrieval_corral))
        final_center_inside_zone = bool(settle_payload.get("final_center_inside_zone", final_center_inside_zone))
        ball_stopped_in_corral = bool(settle_payload.get("ball_stopped_in_corral", ball_stopped_in_corral))
        rolled_away_after_release = bool(settle_payload.get("rolled_away_after_release", rolled_away_after_release))
        retention_pass = (
            int(capture_loss_count) == 0
            and bool(stopped_with_ball_captured)
            and bool(release_started_with_capture)
            if clean_retention_pass is None
            else bool(clean_retention_pass)
        )
        settled_pass = (
            bool(final_inside_retrieval_corral)
            and bool(ball_stopped_in_corral)
            and not bool(rolled_away_after_release)
            and int(post_visit_revisit_count) == 0
            if settled_in_corral_pass is None
            else bool(settled_in_corral_pass)
        )
        if settled_in_corral_pass is None and settle_payload:
            settled_pass = bool(settle_payload.get("settled_in_corral_pass", settled_pass))
        practical_pass = (
            bool(final_inside_retrieval_corral)
            and not bool(rolled_away_after_release)
            and int(post_visit_revisit_count) == 0
            if practical_retrieval_pass is None
            else bool(practical_retrieval_pass)
        )
        fetch_pass = bool(fetch_to_pose_reached)
        if self.mission_objective == MISSION_OBJECTIVE_FETCH_TO_POSE:
            target_pass = fetch_pass
        else:
            target_pass = practical_pass if self.args.scenario_id == "gather_three_ball_zone" else bool(settled_pass)
        resolved_settle_exit_reason = clean_text(
            settle_payload.get("settle_exit_reason") if isinstance(settle_payload, dict) else "",
            clean_text(
                settle_exit_reason,
                default_settle_exit_reason(
                    settled_in_corral_pass=bool(settled_pass),
                    corrected=bool(
                        zone_edge_correction_count
                        or place_controller_reentry_count
                        or int(settle_payload.get("release_recontact_count", 0) or 0)
                    ),
                    rolled_away_after_release=bool(rolled_away_after_release),
                ),
            ),
        )
        payload = {
            "target_id": target.id,
            "label": target.label,
            "pass": bool(target_pass),
            "mission_objective": self.mission_objective,
            "attempts": int(attempts),
            "attempt_kind": str(attempt_kind),
            "capture_loss_count": int(capture_loss_count),
            "route_index": int(route_index),
            "placed": bool(target_pass),
            "fetched": bool(fetch_pass),
            "fetch_to_pose_reached": bool(fetch_pass),
            "fetch_to_pose_time_s": round(float(fetch_to_pose_time_s), 6),
            "fetch_to_pose_failure_reason": clean_text(fetch_to_pose_failure_reason),
            "fetch_pose_world": dict(fetch_pose_world) if isinstance(fetch_pose_world, dict) else {},
            "fetch_delivery_radius_m": round(float(self.fetch_delivery_radius_m), 6),
            "shot_outcome": dict(shot_outcome) if isinstance(shot_outcome, dict) else {},
            "final_ball_pose": final_ball_pose,
            "place_time_s": round(float(place_time_s), 6),
            "local_recovery_attempted": bool(local_recovery_attempted),
            "revisit_attempted": bool(revisit_attempted),
            "surface_profile": self.surface_profile,
            "handoff_kind": clean_text(handoff_kind, "unspecified"),
            "zone_edge_correction_count": int(zone_edge_correction_count),
            "place_controller_reentry_count": int(place_controller_reentry_count),
            "post_visit_revisit_count": int(post_visit_revisit_count),
            "stopped_with_ball_captured": bool(stopped_with_ball_captured),
            "release_started_with_capture": bool(release_started_with_capture),
            "stop_capture_state": stop_capture_state if isinstance(stop_capture_state, dict) else {},
            "release_capture_state": release_capture_state if isinstance(release_capture_state, dict) else {},
            "clean_retention_pass": retention_pass,
            "final_inside_retrieval_corral": bool(final_inside_retrieval_corral),
            "final_center_inside_zone": bool(final_center_inside_zone),
            "ball_stopped_in_corral": bool(ball_stopped_in_corral),
            "rolled_away_after_release": bool(rolled_away_after_release),
            "settled_in_corral_pass": bool(settled_pass),
            "practical_retrieval_pass": bool(practical_pass),
            "settle_exit_reason": resolved_settle_exit_reason,
            "settle_no_chase_activated": bool(settle_no_chase_activated),
            "settle_no_chase_exit_reason": clean_text(settle_no_chase_exit_reason, "none"),
            "release_gate_blocked_reason": clean_text(release_gate_blocked_reason, "none"),
            "pre_stage_pose_world": dict(approach_fields["pre_stage_pose_world"]),
            "pre_stage_pose_reached": bool(approach_fields["pre_stage_pose_reached"]),
            "pre_stage_time_s": round(float(approach_fields["pre_stage_time_s"]), 6),
            "pre_stage_handoff_pass": bool(approach_fields["pre_stage_handoff_pass"]),
            "approach_side_verdict": dict(approach_fields["approach_side_verdict"]),
            "staging_pose_reached": bool(approach_fields["staging_pose_reached"]),
            "entered_goal_side_before_capture": bool(approach_fields["entered_goal_side_before_capture"]),
            "first_contact_push_alignment_deg": clean_number(approach_fields["first_contact_push_alignment_deg"]),
            "push_direction_yaw_deg": round(float(approach_fields["push_direction_yaw_deg"]), 6),
            "stage_time_s": round(float(approach_fields["stage_time_s"]), 6),
            "capture_entry_reached": bool(approach_fields["capture_entry_reached"]),
            "capture_entry_time_s": round(float(approach_fields["capture_entry_time_s"]), 6),
            "approach_failure_reason": clean_text(approach_fields["approach_failure_reason"]),
            "latest_approach_progress": (
                dict(latest_approach_progress)
                if isinstance(latest_approach_progress, dict)
                else {}
            ),
            "fresh_attempt_approach": (
                dict(fresh_attempt_approach)
                if isinstance(fresh_attempt_approach, dict)
                else {}
            ),
        }
        if settle_payload:
            payload.update(settle_payload)
            payload["settle_exit_reason"] = clean_text(payload.get("settle_exit_reason"), resolved_settle_exit_reason)
        return payload

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None, timeout_s: float | None = None) -> tuple[int, dict[str, Any]]:
        return http_json(
            f"{self.dashboard_url}{path}",
            method=method,
            payload=payload,
            timeout_s=timeout_s or self.args.timeout_s,
        )

    def _wait_for_state(self, predicate, timeout_s: float, error_text: str) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            if predicate(last_state):
                return last_state
            time.sleep(0.5)
        raise RuntimeError(error_text + f" Last state: {json.dumps(last_state, sort_keys=True)}")

    def _ensure_environment_ready(self) -> tuple[dict[str, Any], bool]:
        state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
        if state.get("environment_state") == "environment_ready":
            return state, False
        status, payload = self._request("POST", "/api/env/start", timeout_s=10.0)
        if status not in {200, 202}:
            raise RuntimeError(f"Failed to start environment: {payload}")
        ready_state = self._wait_for_state(
            lambda current: current.get("environment_state") == "environment_ready" and current.get("session_id"),
            timeout_s=self.args.environment_timeout_s,
            error_text="Environment did not become ready for gather mission.",
        )
        return ready_state, True

    def _wait_for_robot_pose(self, timeout_s: float) -> dict[str, Any]:
        return self._wait_for_state(
            lambda current: (
                current.get("environment_state") == "environment_ready"
                and isinstance(current.get("belief"), dict)
                and isinstance(current.get("belief", {}).get("latest_robot_pose"), dict)
                and current.get("compose_project")
            ),
            timeout_s=timeout_s,
            error_text="Robot pose did not become available for gather mission.",
        )

    def _wait_for_robot_pose_near(
        self,
        *,
        x: float,
        y: float,
        yaw: float,
        timeout_s: float = 15.0,
        position_tolerance_m: float = 0.15,
        yaw_tolerance_rad: float = 0.35,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            try:
                robot_x, robot_y, robot_yaw = self._robot_pose_components(last_state)
            except RuntimeError:
                time.sleep(self.args.poll_s)
                continue
            position_error = math.hypot(robot_x - x, robot_y - y)
            yaw_error = abs(normalize_angle(robot_yaw - yaw))
            if position_error <= position_tolerance_m and yaw_error <= yaw_tolerance_rad:
                return last_state
            time.sleep(self.args.poll_s)
        raise RuntimeError(f"Robot pose did not settle near commanded start pose: {last_state}")

    def _wait_for_nav2_ready(self, timeout_s: float = 30.0) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            brain = last_state.get("brain", {}) if isinstance(last_state.get("brain"), dict) else {}
            if bool(brain.get("nav2_server_ready", False)):
                return last_state
            time.sleep(0.5)
        return last_state

    def _wait_for_pursuit_quiet(self, timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            brain = last_state.get("brain", {}) if isinstance(last_state.get("brain"), dict) else {}
            outcome = last_state.get("outcome", {}) if isinstance(last_state.get("outcome"), dict) else {}
            if (
                not bool(brain.get("goal_in_progress", False))
                and not bool(brain.get("track_active", False))
                and not bool(outcome.get("nav_goal_recent", False))
                and not bool(outcome.get("cmd_vel_recent", False))
            ):
                return last_state
            time.sleep(0.25)
        return last_state

    def _inter_target_quiet_timeout_s(self) -> float:
        if self.args.scenario_id == "gather_three_ball_zone":
            return min(float(self.args.pursuit_settle_timeout_s), 1.0)
        return float(self.args.pursuit_settle_timeout_s)

    def _stop_environment(self) -> None:
        self._request("POST", "/api/env/stop", timeout_s=10.0)
        self._wait_for_state(
            lambda current: current.get("environment_state") == "stopped",
            timeout_s=240.0,
            error_text="Environment did not stop cleanly after gather mission.",
        )

    def _container_id(self, project_name: str, service_name: str) -> str:
        proc = subprocess.run(
            [self.docker, "compose", "-f", str(REPO_ROOT / "docker-compose.yml"), "-p", project_name, "ps", "-q", service_name],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Unable to resolve container id for {service_name}: {proc.stdout}\n{proc.stderr}")
        container_ids = proc.stdout.strip().splitlines()
        if not container_ids:
            raise RuntimeError(f"No running container id found for {service_name}.")
        return container_ids[0].strip()

    def _docker_exec(self, container_id: str, script: str) -> tuple[int, str]:
        proc = subprocess.run(
            [
                self.docker,
                "exec",
                "-i",
                container_id,
                "bash",
                "-lc",
                "cat >/tmp/chasecar_gather_mission.sh && chmod +x /tmp/chasecar_gather_mission.sh && /tmp/chasecar_gather_mission.sh",
            ],
            cwd=str(REPO_ROOT),
            input=script.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        output = (proc.stdout or b"").decode("utf-8", errors="replace")
        output += ("\n" + (proc.stderr or b"").decode("utf-8", errors="replace")) if proc.stderr else ""
        return proc.returncode, output.strip()

    def _docker_logs_since(self, container_id: str, since_utc: datetime, *, tail: int = 400) -> dict[str, Any]:
        since_text = since_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        proc = subprocess.run(
            [
                self.docker,
                "logs",
                "--since",
                since_text,
                "--tail",
                str(max(int(tail), 1)),
                container_id,
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            check=False,
        )
        output = (proc.stdout or b"").decode("utf-8", errors="replace")
        output += ("\n" + (proc.stderr or b"").decode("utf-8", errors="replace")) if proc.stderr else ""
        raw_lines = [line.strip() for line in output.splitlines() if line.strip()]
        needles = (
            "controller_server",
            "mppifollowpath",
            "mppi",
            "followpath",
            "goal_status",
            "aborted",
            "error",
            "warn",
            "failed",
        )
        excerpt = [
            line[-600:]
            for line in raw_lines
            if any(needle in line.lower() for needle in needles)
        ]
        return {
            "returncode": int(proc.returncode),
            "since_utc": since_text,
            "raw_line_count": len(raw_lines),
            "excerpt_line_count": len(excerpt[-80:]),
            "excerpt": excerpt[-80:],
            "error": "" if proc.returncode == 0 else output[-1200:],
        }

    def _safe_stop(self) -> None:
        try:
            self._request("POST", "/api/intents/dispatch", {"intent": "safe_stop", "args": {}}, timeout_s=10.0)
        except Exception:
            pass

    def _parse_nav2_reacquire_result(self, output: str, *, rc: int) -> dict[str, Any]:
        for line in reversed(str(output or "").splitlines()):
            line = line.strip()
            if not line.startswith(NAV2_REACQUIRE_RESULT_MARKER):
                continue
            raw = line[len(NAV2_REACQUIRE_RESULT_MARKER):].strip()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                break
            if isinstance(payload, dict):
                payload.setdefault("process_returncode", int(rc))
                return payload
        return {
            "dispatch_status": "client_error",
            "accepted": False,
            "success": False,
            "status_code": None,
            "elapsed_s": 0.0,
            "error": clean_text(output, "missing_nav2_reacquire_result"),
            "process_returncode": int(rc),
        }

    def _dispatch_nav2_reacquire_goal(
        self,
        *,
        compose_project: str,
        goal_pose: dict[str, Any],
        timeout_s: float,
    ) -> dict[str, Any]:
        gate_stack_container = self._container_id(compose_project, "gate-stack")
        payload = {
            "goal_pose": {
                "frame_id": clean_text(goal_pose.get("frame_id"), "odom"),
                "x": float(clean_number(goal_pose.get("x")) or 0.0),
                "y": float(clean_number(goal_pose.get("y")) or 0.0),
                "yaw": float(clean_number(goal_pose.get("yaw")) or 0.0),
            },
            "server_wait_s": float(DEFAULT_NAV2_REACQUIRE_SERVER_WAIT_S),
            "timeout_s": float(max(timeout_s, 0.1)),
        }
        script = (
            "set -eo pipefail\n"
            "set +u\n"
            "source /opt/ros/${CORE_ROS_DISTRO:-kilted}/setup.bash\n"
            "if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi\n"
            "set -u\n"
            f"export NAV2_REACQUIRE_PAYLOAD={shlex.quote(json.dumps(payload, separators=(',', ':')))}\n"
            r"""python3 - <<'PY'
import json
import math
import os
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter

MARKER = "NAV2_REACQUIRE_RESULT="


def yaw_to_quaternion(yaw):
    half = 0.5 * float(yaw)
    return 0.0, 0.0, math.sin(half), math.cos(half)


def wait_future(node, future, timeout_s):
    deadline = time.monotonic() + max(float(timeout_s), 0.1)
    while time.monotonic() < deadline and rclpy.ok():
        if future.done():
            return True
        rclpy.spin_once(node, timeout_sec=0.1)
    return bool(future.done())


def emit(payload):
    print(MARKER + json.dumps(payload, sort_keys=True), flush=True)


payload = json.loads(os.environ["NAV2_REACQUIRE_PAYLOAD"])
goal_pose = payload["goal_pose"]
started = time.monotonic()
rclpy.init()
node = Node("gather_nav2_reacquire_goal_client")
node.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])
client = ActionClient(node, NavigateToPose, "/navigate_to_pose")
try:
    server_ready = bool(client.wait_for_server(timeout_sec=max(float(payload["server_wait_s"]), 0.1)))
    if not server_ready:
        emit({
            "dispatch_status": "server_unavailable",
            "accepted": False,
            "success": False,
            "status_code": int(GoalStatus.STATUS_UNKNOWN),
            "elapsed_s": round(time.monotonic() - started, 6),
            "error": "nav2_action_server_unavailable",
        })
    else:
        goal = NavigateToPose.Goal()
        pose = PoseStamped()
        pose.header.frame_id = str(goal_pose.get("frame_id") or "odom")
        pose.header.stamp = node.get_clock().now().to_msg()
        pose.pose.position.x = float(goal_pose["x"])
        pose.pose.position.y = float(goal_pose["y"])
        pose.pose.position.z = 0.0
        qx, qy, qz, qw = yaw_to_quaternion(float(goal_pose["yaw"]))
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        goal.pose = pose
        goal.behavior_tree = ""
        send_future = client.send_goal_async(goal)
        if not wait_future(node, send_future, timeout_s=5.0):
            emit({
                "dispatch_status": "send_goal_timeout",
                "accepted": False,
                "success": False,
                "status_code": int(GoalStatus.STATUS_UNKNOWN),
                "elapsed_s": round(time.monotonic() - started, 6),
                "error": "send_goal_timeout",
            })
        else:
            goal_handle = send_future.result()
            if goal_handle is None:
                emit({
                    "dispatch_status": "send_goal_result_none",
                    "accepted": False,
                    "success": False,
                    "status_code": int(GoalStatus.STATUS_UNKNOWN),
                    "elapsed_s": round(time.monotonic() - started, 6),
                    "error": "send_goal_result_none",
                })
            elif not goal_handle.accepted:
                emit({
                    "dispatch_status": "goal_rejected",
                    "accepted": False,
                    "success": False,
                    "status_code": int(GoalStatus.STATUS_REJECTED),
                    "elapsed_s": round(time.monotonic() - started, 6),
                    "error": "goal_rejected",
                })
            else:
                result_future = goal_handle.get_result_async()
                if not wait_future(node, result_future, timeout_s=float(payload["timeout_s"])):
                    try:
                        goal_handle.cancel_goal_async()
                    except Exception:
                        pass
                    emit({
                        "dispatch_status": "goal_result_timeout",
                        "accepted": True,
                        "success": False,
                        "status_code": int(GoalStatus.STATUS_ABORTED),
                        "elapsed_s": round(time.monotonic() - started, 6),
                        "error": "goal_result_timeout",
                    })
                else:
                    result = result_future.result()
                    status_code = int(result.status) if result is not None else int(GoalStatus.STATUS_UNKNOWN)
                    success = status_code == int(GoalStatus.STATUS_SUCCEEDED)
                    emit({
                        "dispatch_status": "goal_succeeded" if success else "goal_finished",
                        "accepted": True,
                        "success": bool(success),
                        "status_code": status_code,
                        "elapsed_s": round(time.monotonic() - started, 6),
                        "error": "" if success else f"goal_status_{status_code}",
                    })
finally:
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
PY
"""
        )
        rc, output = self._docker_exec(gate_stack_container, script)
        result = self._parse_nav2_reacquire_result(output, rc=rc)
        result.setdefault("goal_pose", dict(goal_pose))
        return result

    def _parse_nav2_follow_path_result(self, output: str, *, rc: int) -> dict[str, Any]:
        for line in reversed(str(output or "").splitlines()):
            line = line.strip()
            if not line.startswith(NAV2_FOLLOW_PATH_RESULT_MARKER):
                continue
            raw = line[len(NAV2_FOLLOW_PATH_RESULT_MARKER):].strip()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                break
            if isinstance(payload, dict):
                payload.setdefault("process_returncode", int(rc))
                return payload
        return {
            "dispatch_status": "client_error",
            "accepted": False,
            "success": False,
            "status_code": None,
            "elapsed_s": 0.0,
            "error": clean_text(output, "missing_nav2_follow_path_result"),
            "process_returncode": int(rc),
        }

    def _dispatch_nav2_follow_path_reacquire(
        self,
        *,
        compose_project: str,
        path_poses: list[dict[str, Any]],
        controller_id: str,
        goal_checker_id: str,
        timeout_s: float,
    ) -> dict[str, Any]:
        if not path_poses:
            return {
                "dispatch_status": "empty_path",
                "accepted": False,
                "success": False,
                "status_code": None,
                "elapsed_s": 0.0,
                "error": "follow_path_empty_path",
            }
        gate_stack_container = self._container_id(compose_project, "gate-stack")
        payload = {
            "path_poses": [
                {
                    "frame_id": clean_text(pose.get("frame_id"), "odom"),
                    "x": float(clean_number(pose.get("x")) or 0.0),
                    "y": float(clean_number(pose.get("y")) or 0.0),
                    "yaw": float(clean_number(pose.get("yaw")) or 0.0),
                    "kind": clean_text(pose.get("kind")),
                }
                for pose in path_poses
                if isinstance(pose, dict)
            ],
            "controller_id": clean_text(controller_id, "FollowPath"),
            "goal_checker_id": clean_text(goal_checker_id, DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID),
            "server_wait_s": float(DEFAULT_NAV2_FOLLOW_PATH_SERVER_WAIT_S),
            "timeout_s": float(max(timeout_s, 0.1)),
            "feedback_sample_max": int(DEFAULT_NAV2_FOLLOW_PATH_FEEDBACK_SAMPLE_MAX),
            "feedback_sample_interval_s": float(DEFAULT_NAV2_FOLLOW_PATH_FEEDBACK_SAMPLE_INTERVAL_S),
            "diagnostic_sample_max": int(DEFAULT_NAV2_FOLLOW_PATH_DIAGNOSTIC_SAMPLE_MAX),
            "diagnostic_sample_interval_s": float(DEFAULT_NAV2_FOLLOW_PATH_DIAGNOSTIC_SAMPLE_INTERVAL_S),
            "cmd_vel_topics": ["/cmd_vel_nav", "/cmd_vel", "/jetbot_base_controller/cmd_vel"],
            "odom_topic": "/jetbot_base_controller/odom",
        }
        log_since_utc = datetime.now(timezone.utc)
        script = (
            "set -eo pipefail\n"
            "set +u\n"
            "source /opt/ros/${CORE_ROS_DISTRO:-kilted}/setup.bash\n"
            "if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi\n"
            "set -u\n"
            f"export NAV2_FOLLOW_PATH_PAYLOAD={shlex.quote(json.dumps(payload, separators=(',', ':')))}\n"
            r"""python3 - <<'PY'
import json
import math
import os
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from nav_msgs.msg import Path
from nav2_msgs.action import FollowPath
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter

MARKER = "NAV2_FOLLOW_PATH_RESULT="
STATUS_TEXT = {
    int(GoalStatus.STATUS_UNKNOWN): "STATUS_UNKNOWN",
    int(GoalStatus.STATUS_ACCEPTED): "STATUS_ACCEPTED",
    int(GoalStatus.STATUS_EXECUTING): "STATUS_EXECUTING",
    int(GoalStatus.STATUS_CANCELING): "STATUS_CANCELING",
    int(GoalStatus.STATUS_SUCCEEDED): "STATUS_SUCCEEDED",
    int(GoalStatus.STATUS_CANCELED): "STATUS_CANCELED",
    int(GoalStatus.STATUS_ABORTED): "STATUS_ABORTED",
}


def ros_to_plain(value, depth=0):
    if depth > 4:
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [ros_to_plain(item, depth + 1) for item in list(value)[:20]]
    if isinstance(value, dict):
        return {str(key): ros_to_plain(item, depth + 1) for key, item in value.items()}
    if hasattr(value, "sec") and hasattr(value, "nanosec"):
        return {"sec": int(value.sec), "nanosec": int(value.nanosec)}
    field_names = []
    if hasattr(value, "get_fields_and_field_types"):
        try:
            field_names = list(value.get_fields_and_field_types().keys())
        except Exception:
            field_names = []
    if not field_names and hasattr(value, "__slots__"):
        field_names = [str(slot).lstrip("_") for slot in value.__slots__]
    if field_names:
        payload = {}
        for name in field_names:
            try:
                payload[name] = ros_to_plain(getattr(value, name), depth + 1)
            except Exception as exc:
                payload[name] = f"<unreadable:{exc}>"
        return payload
    return str(value)


def yaw_to_quaternion(yaw):
    half = 0.5 * float(yaw)
    return 0.0, 0.0, math.sin(half), math.cos(half)


def quaternion_to_yaw(q):
    siny_cosp = 2.0 * ((q.w * q.z) + (q.x * q.y))
    cosy_cosp = 1.0 - (2.0 * ((q.y * q.y) + (q.z * q.z)))
    return math.atan2(siny_cosp, cosy_cosp)


def normalize_angle(value):
    result = math.fmod(float(value) + math.pi, 2.0 * math.pi)
    if result < 0.0:
        result += 2.0 * math.pi
    return result - math.pi


def status_text(status_code):
    return STATUS_TEXT.get(int(status_code), f"STATUS_{int(status_code)}")


def append_ring(buffer, sample, limit):
    if limit <= 0:
        return
    buffer.append(sample)
    while len(buffer) > limit:
        buffer.pop(0)


def path_progress_for_pose(x, y, yaw):
    if not path_poses:
        return {}
    nearest_index = 0
    nearest_distance = None
    for index, item in enumerate(path_poses):
        dx = float(item.get("x", 0.0)) - float(x)
        dy = float(item.get("y", 0.0)) - float(y)
        distance = math.hypot(dx, dy)
        if nearest_distance is None or distance < nearest_distance:
            nearest_index = index
            nearest_distance = distance
    terminal = path_poses[-1]
    terminal_dx = float(terminal.get("x", 0.0)) - float(x)
    terminal_dy = float(terminal.get("y", 0.0)) - float(y)
    terminal_yaw_error = normalize_angle(float(yaw) - float(terminal.get("yaw", 0.0)))
    nearest = path_poses[nearest_index]
    return {
        "nearest_path_index": int(nearest_index),
        "nearest_path_kind": str(nearest.get("kind", "")),
        "nearest_path_distance_m": round(float(nearest_distance or 0.0), 6),
        "remaining_path_pose_count": int(max(len(path_poses) - nearest_index - 1, 0)),
        "terminal_path_distance_m": round(math.hypot(terminal_dx, terminal_dy), 6),
        "terminal_yaw_error_deg": round(math.degrees(terminal_yaw_error), 6),
    }


def twist_payload(msg):
    twist = msg.twist if hasattr(msg, "twist") else msg
    return {
        "linear_x": round(float(twist.linear.x), 6),
        "linear_y": round(float(twist.linear.y), 6),
        "linear_z": round(float(twist.linear.z), 6),
        "angular_x": round(float(twist.angular.x), 6),
        "angular_y": round(float(twist.angular.y), 6),
        "angular_z": round(float(twist.angular.z), 6),
    }


def wait_future(node, future, timeout_s):
    deadline = time.monotonic() + max(float(timeout_s), 0.1)
    while time.monotonic() < deadline and rclpy.ok():
        if future.done():
            return True
        rclpy.spin_once(node, timeout_sec=0.1)
    return bool(future.done())


def emit(payload):
    print(MARKER + json.dumps(payload, sort_keys=True), flush=True)


payload = json.loads(os.environ["NAV2_FOLLOW_PATH_PAYLOAD"])
path_poses = payload.get("path_poses", [])
feedback_sample_max = max(int(payload.get("feedback_sample_max") or 0), 0)
feedback_sample_interval_s = max(float(payload.get("feedback_sample_interval_s") or 0.0), 0.0)
diagnostic_sample_max = max(int(payload.get("diagnostic_sample_max") or 0), 0)
diagnostic_sample_interval_s = max(float(payload.get("diagnostic_sample_interval_s") or 0.0), 0.0)
feedback_count = 0
feedback_samples = []
feedback_last = {}
last_feedback_sample_elapsed_s = -999999.0
cmd_vel_counts = {}
cmd_vel_samples = []
cmd_vel_last = {}
odom_count = 0
odom_samples = []
odom_last = {}
odom_first = {}
path_progress_samples = []
path_progress_last = {}
last_cmd_vel_sample_elapsed_s = -999999.0
last_odom_sample_elapsed_s = -999999.0
started = time.monotonic()
rclpy.init()
node = Node("gather_nav2_follow_path_reacquire_client")
node.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])
client = ActionClient(node, FollowPath, "/follow_path")


def odom_delta_payload():
    if not odom_first or not odom_last:
        return {}
    dx = float(odom_last.get("x", 0.0)) - float(odom_first.get("x", 0.0))
    dy = float(odom_last.get("y", 0.0)) - float(odom_first.get("y", 0.0))
    dyaw = normalize_angle(float(odom_last.get("yaw", 0.0)) - float(odom_first.get("yaw", 0.0)))
    return {
        "dx_m": round(dx, 6),
        "dy_m": round(dy, 6),
        "distance_m": round(math.hypot(dx, dy), 6),
        "dyaw_deg": round(math.degrees(dyaw), 6),
        "elapsed_s": round(float(odom_last.get("elapsed_s", 0.0)) - float(odom_first.get("elapsed_s", 0.0)), 6),
    }


def result_payload(extra):
    result = dict(extra)
    if "status_text" not in result and result.get("status_code") is not None:
        result["status_text"] = status_text(int(result["status_code"]))
    result.setdefault("feedback_count", int(feedback_count))
    result.setdefault("feedback_samples", feedback_samples)
    result.setdefault("feedback_last", feedback_last)
    result.setdefault("feedback_sample_max", int(feedback_sample_max))
    result.setdefault("feedback_sample_interval_s", round(float(feedback_sample_interval_s), 6))
    result.setdefault("diagnostic_sample_max", int(diagnostic_sample_max))
    result.setdefault("diagnostic_sample_interval_s", round(float(diagnostic_sample_interval_s), 6))
    result.setdefault("cmd_vel_counts", dict(cmd_vel_counts))
    result.setdefault("cmd_vel_samples", cmd_vel_samples)
    result.setdefault("cmd_vel_last", cmd_vel_last)
    result.setdefault("odom_count", int(odom_count))
    result.setdefault("odom_samples", odom_samples)
    result.setdefault("odom_last", odom_last)
    result.setdefault("odom_delta", odom_delta_payload())
    result.setdefault("path_progress_samples", path_progress_samples)
    result.setdefault("path_progress_last", path_progress_last)
    result.setdefault("timeout_s", round(float(payload.get("timeout_s") or 0.0), 6))
    return result


def feedback_callback(feedback_msg):
    global feedback_count, feedback_last, last_feedback_sample_elapsed_s
    feedback_count += 1
    elapsed_s = round(time.monotonic() - started, 6)
    sample = {
        "elapsed_s": elapsed_s,
        "feedback": ros_to_plain(getattr(feedback_msg, "feedback", feedback_msg)),
    }
    feedback_last = sample
    if len(feedback_samples) >= feedback_sample_max:
        return
    if not feedback_samples or elapsed_s - last_feedback_sample_elapsed_s >= feedback_sample_interval_s:
        feedback_samples.append(sample)
        last_feedback_sample_elapsed_s = elapsed_s


def make_cmd_callback(topic):
    def _callback(msg):
        global cmd_vel_last, last_cmd_vel_sample_elapsed_s
        elapsed_s = round(time.monotonic() - started, 6)
        cmd_vel_counts[topic] = int(cmd_vel_counts.get(topic, 0)) + 1
        sample = {"elapsed_s": elapsed_s, "topic": topic, **twist_payload(msg)}
        cmd_vel_last = sample
        if elapsed_s - last_cmd_vel_sample_elapsed_s >= diagnostic_sample_interval_s:
            append_ring(cmd_vel_samples, sample, diagnostic_sample_max)
            last_cmd_vel_sample_elapsed_s = elapsed_s
    return _callback


def odom_callback(msg):
    global odom_count, odom_first, odom_last, path_progress_last, last_odom_sample_elapsed_s
    odom_count += 1
    elapsed_s = round(time.monotonic() - started, 6)
    pose = msg.pose.pose
    twist = msg.twist.twist
    yaw = quaternion_to_yaw(pose.orientation)
    sample = {
        "elapsed_s": elapsed_s,
        "x": round(float(pose.position.x), 6),
        "y": round(float(pose.position.y), 6),
        "yaw": round(float(yaw), 6),
        "linear_x": round(float(twist.linear.x), 6),
        "angular_z": round(float(twist.angular.z), 6),
    }
    progress = path_progress_for_pose(sample["x"], sample["y"], yaw)
    if progress:
        sample["path_progress"] = progress
        path_progress_last = {"elapsed_s": elapsed_s, **progress}
        if progress.get("terminal_path_distance_m", 999.0) <= 1.5:
            append_ring(path_progress_samples, path_progress_last, diagnostic_sample_max)
    if not odom_first:
        odom_first = dict(sample)
    odom_last = dict(sample)
    if elapsed_s - last_odom_sample_elapsed_s >= diagnostic_sample_interval_s:
        append_ring(odom_samples, sample, diagnostic_sample_max)
        last_odom_sample_elapsed_s = elapsed_s


for topic in payload.get("cmd_vel_topics", []):
    topic = str(topic)
    cmd_vel_counts[topic] = 0
    if topic == "/jetbot_base_controller/cmd_vel":
        node.create_subscription(TwistStamped, topic, make_cmd_callback(topic), 20)
    else:
        node.create_subscription(Twist, topic, make_cmd_callback(topic), 20)
node.create_subscription(Odometry, str(payload.get("odom_topic") or "/jetbot_base_controller/odom"), odom_callback, 20)


try:
    if not path_poses:
        emit(result_payload({
            "dispatch_status": "empty_path",
            "accepted": False,
            "success": False,
            "status_code": int(GoalStatus.STATUS_UNKNOWN),
            "elapsed_s": round(time.monotonic() - started, 6),
            "error": "follow_path_empty_path",
        }))
    else:
        server_ready = bool(client.wait_for_server(timeout_sec=max(float(payload["server_wait_s"]), 0.1)))
        if not server_ready:
            emit(result_payload({
                "dispatch_status": "server_unavailable",
                "accepted": False,
                "success": False,
                "status_code": int(GoalStatus.STATUS_UNKNOWN),
                "elapsed_s": round(time.monotonic() - started, 6),
                "error": "follow_path_action_server_unavailable",
            }))
        else:
            now = node.get_clock().now().to_msg()
            frame_id = str(path_poses[0].get("frame_id") or "odom")
            path = Path()
            path.header.frame_id = frame_id
            path.header.stamp = now
            for item in path_poses:
                pose = PoseStamped()
                pose.header.frame_id = str(item.get("frame_id") or frame_id)
                pose.header.stamp = now
                pose.pose.position.x = float(item["x"])
                pose.pose.position.y = float(item["y"])
                pose.pose.position.z = 0.0
                qx, qy, qz, qw = yaw_to_quaternion(float(item["yaw"]))
                pose.pose.orientation.x = qx
                pose.pose.orientation.y = qy
                pose.pose.orientation.z = qz
                pose.pose.orientation.w = qw
                path.poses.append(pose)
            goal = FollowPath.Goal()
            goal.path = path
            goal.controller_id = str(payload.get("controller_id") or "FollowPath")
            goal.goal_checker_id = str(payload.get("goal_checker_id") or "general_goal_checker")
            if hasattr(goal, "progress_checker_id"):
                goal.progress_checker_id = ""
            send_future = client.send_goal_async(goal, feedback_callback=feedback_callback)
            if not wait_future(node, send_future, timeout_s=5.0):
                emit(result_payload({
                    "dispatch_status": "send_goal_timeout",
                    "accepted": False,
                    "success": False,
                    "status_code": int(GoalStatus.STATUS_UNKNOWN),
                    "elapsed_s": round(time.monotonic() - started, 6),
                    "error": "send_goal_timeout",
                }))
            else:
                goal_handle = send_future.result()
                if goal_handle is None:
                    emit(result_payload({
                        "dispatch_status": "send_goal_result_none",
                        "accepted": False,
                        "success": False,
                        "status_code": int(GoalStatus.STATUS_UNKNOWN),
                        "elapsed_s": round(time.monotonic() - started, 6),
                        "error": "send_goal_result_none",
                    }))
                elif not goal_handle.accepted:
                    emit(result_payload({
                        "dispatch_status": "goal_rejected",
                        "accepted": False,
                        "success": False,
                        "status_code": int(GoalStatus.STATUS_REJECTED),
                        "elapsed_s": round(time.monotonic() - started, 6),
                        "error": "goal_rejected",
                    }))
                else:
                    result_future = goal_handle.get_result_async()
                    if not wait_future(node, result_future, timeout_s=float(payload["timeout_s"])):
                        cancel_started = time.monotonic()
                        cancel_response_received = False
                        cancel_goal_count = 0
                        try:
                            cancel_future = goal_handle.cancel_goal_async()
                            cancel_response_received = wait_future(node, cancel_future, timeout_s=1.0)
                            if cancel_response_received and cancel_future.result() is not None:
                                cancel_goal_count = len(getattr(cancel_future.result(), "goals_canceling", []) or [])
                        except Exception as exc:
                            cancel_error = str(exc)
                        else:
                            cancel_error = ""
                        emit(result_payload({
                            "dispatch_status": "goal_result_timeout",
                            "accepted": True,
                            "success": False,
                            "status_code": int(GoalStatus.STATUS_ABORTED),
                            "status_text": status_text(int(GoalStatus.STATUS_ABORTED)),
                            "elapsed_s": round(time.monotonic() - started, 6),
                            "error": "goal_result_timeout",
                            "timed_out": True,
                            "cancel_requested": True,
                            "cancel_response_received": bool(cancel_response_received),
                            "cancel_goal_count": int(cancel_goal_count),
                            "cancel_elapsed_s": round(time.monotonic() - cancel_started, 6),
                            "cancel_error": cancel_error,
                        }))
                    else:
                        result = result_future.result()
                        status_code = int(result.status) if result is not None else int(GoalStatus.STATUS_UNKNOWN)
                        success = status_code == int(GoalStatus.STATUS_SUCCEEDED)
                        emit(result_payload({
                            "dispatch_status": "goal_succeeded" if success else "goal_finished",
                            "accepted": True,
                            "success": bool(success),
                            "status_code": status_code,
                            "status_text": status_text(status_code),
                            "action_result": ros_to_plain(getattr(result, "result", None)),
                            "elapsed_s": round(time.monotonic() - started, 6),
                            "error": "" if success else f"goal_status_{status_code}",
                            "timed_out": False,
                            "cancel_requested": False,
                        }))
finally:
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
PY
"""
        )
        rc, output = self._docker_exec(gate_stack_container, script)
        result = self._parse_nav2_follow_path_result(output, rc=rc)
        result.setdefault(
            "controller_log_excerpt",
            self._docker_logs_since(
                gate_stack_container,
                log_since_utc,
                tail=DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_LOG_TAIL,
            ),
        )
        result.setdefault("path_pose_count", len(payload["path_poses"]))
        result.setdefault("controller_id", payload["controller_id"])
        result.setdefault("goal_checker_id", payload["goal_checker_id"])
        result.setdefault("feedback_count", 0)
        result.setdefault("feedback_samples", [])
        result.setdefault("feedback_last", {})
        result.setdefault("feedback_sample_max", payload["feedback_sample_max"])
        result.setdefault("feedback_sample_interval_s", payload["feedback_sample_interval_s"])
        result.setdefault("diagnostic_sample_max", payload["diagnostic_sample_max"])
        result.setdefault("diagnostic_sample_interval_s", payload["diagnostic_sample_interval_s"])
        result.setdefault("cmd_vel_counts", {})
        result.setdefault("cmd_vel_samples", [])
        result.setdefault("cmd_vel_last", {})
        result.setdefault("odom_count", 0)
        result.setdefault("odom_samples", [])
        result.setdefault("odom_last", {})
        result.setdefault("odom_delta", {})
        result.setdefault("path_progress_samples", [])
        result.setdefault("path_progress_last", {})
        result.setdefault("timeout_s", payload["timeout_s"])
        result.setdefault("cancel_requested", False)
        return result

    def _robot_pose_components(self, state: dict[str, Any]) -> tuple[float, float, float]:
        belief = state.get("belief", {}) if isinstance(state.get("belief"), dict) else {}
        robot_pose = belief.get("latest_robot_pose", {}) if isinstance(belief.get("latest_robot_pose"), dict) else {}
        robot_x = clean_number(robot_pose.get("x"))
        robot_y = clean_number(robot_pose.get("y"))
        robot_yaw = clean_number(robot_pose.get("yaw"))
        if robot_x is None or robot_y is None or robot_yaw is None:
            raise RuntimeError("Robot pose unavailable for gather mission.")
        return robot_x, robot_y, robot_yaw

    def _set_robot_pose(self, state: dict[str, Any], *, x: float, y: float, yaw: float) -> None:
        compose_project = clean_text(state.get("compose_project"))
        if not compose_project:
            raise RuntimeError("Active compose project missing from dashboard state.")
        world_name = clean_text(state.get("world_name"), DEFAULT_WORLD_NAME)
        sim_gate_container = self._container_id(compose_project, "sim-gate")
        half_yaw = 0.5 * yaw
        robot_qz = math.sin(half_yaw)
        robot_qw = math.cos(half_yaw)
        script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
WORLD_NAME={json.dumps(world_name)}
ROBOT_X={json.dumps(f"{x:.6f}")}
ROBOT_Y={json.dumps(f"{y:.6f}")}
ROBOT_QZ={json.dumps(f"{robot_qz:.6f}")}
ROBOT_QW={json.dumps(f"{robot_qw:.6f}")}
if command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"jetbot\\" position {{ x: $ROBOT_X y: $ROBOT_Y z: 0.0 }} orientation {{ x: 0 y: 0 z: $ROBOT_QZ w: $ROBOT_QW }}"
fi
"""
        rc, output = self._docker_exec(sim_gate_container, script)
        if rc != 0:
            raise RuntimeError(f"Failed to set robot pose: {output}")

    def _spawn_model(
        self,
        *,
        compose_project: str,
        world_name: str,
        model_sdf_host: Path,
        model_name: str,
        x: float,
        y: float,
        z: float,
        yaw: float,
        log_path: Path,
    ) -> dict[str, Any]:
        sim_gate_container = self._container_id(compose_project, "sim-gate")
        model_sdf = to_container_repo_path(model_sdf_host.resolve())
        half_yaw = 0.5 * yaw
        qz = math.sin(half_yaw)
        qw = math.cos(half_yaw)
        script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
MODEL_FILE={json.dumps(model_sdf)}
MODEL_NAME={json.dumps(model_name)}
WORLD_NAME={json.dumps(world_name)}
TARGET_X={json.dumps(f"{x:.6f}")}
TARGET_Y={json.dumps(f"{y:.6f}")}
TARGET_Z={json.dumps(f"{z:.6f}")}
TARGET_QZ={json.dumps(f"{qz:.6f}")}
TARGET_QW={json.dumps(f"{qw:.6f}")}
if command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" type: 2" >/dev/null 2>&1 || true
fi
spawn_create() {{
  local include_world="$1"
  local -a cmd=(ros2 run ros_gz_sim create)
  if [[ "$include_world" == "true" ]]; then
    cmd+=(-world "$WORLD_NAME")
  fi
  cmd+=(-file "$MODEL_FILE" -name "$MODEL_NAME" -x "$TARGET_X" -y "$TARGET_Y" -z "$TARGET_Z")
  "${{cmd[@]}}"
}}
set +e
spawn_create true > /tmp/chasecar_gather_spawn.log 2>&1
rc=$?
if [[ "$rc" -ne 0 ]] && grep -Eq 'Waiting for service \\[/world/.*/create\\] to become available' /tmp/chasecar_gather_spawn.log 2>/dev/null; then
  spawn_create false >> /tmp/chasecar_gather_spawn.log 2>&1
  rc=$?
fi
if [[ "$rc" -eq 0 ]] && command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" position {{ x: $TARGET_X y: $TARGET_Y z: $TARGET_Z }} orientation {{ x: 0 y: 0 z: $TARGET_QZ w: $TARGET_QW }}" >> /tmp/chasecar_gather_spawn.log 2>&1
  setpose_rc=$?
  if [[ "$setpose_rc" -ne 0 ]]; then
    rc="$setpose_rc"
  fi
fi
cat /tmp/chasecar_gather_spawn.log
exit "$rc"
"""
        rc, output = self._docker_exec(sim_gate_container, script)
        log_path.write_text(output + "\n", encoding="utf-8")
        payload = {
            "generated_utc": utc_now(),
            "compose_project": compose_project,
            "world_name": world_name,
            "model_name": model_name,
            "model_sdf": str(model_sdf_host.resolve()),
            "world_pose": {"x": x, "y": y, "z": z, "yaw": yaw},
            "spawn_rc": rc,
            "log_path": str(log_path),
            "output": output,
            "pass": rc == 0,
        }
        if rc != 0:
            raise RuntimeError(f"Failed to spawn model {model_name}: {output}")
        return payload

    def _remove_model(self, *, compose_project: str, world_name: str, model_name: str) -> None:
        sim_gate_container = self._container_id(compose_project, "sim-gate")
        script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
WORLD_NAME={json.dumps(world_name)}
MODEL_NAME={json.dumps(model_name)}
if command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" type: 2" || true
fi
"""
        self._docker_exec(sim_gate_container, script)

    def _target_model_name(self, target: GatherTargetSpec) -> str:
        safe_id = "".join(ch if ch.isalnum() else "_" for ch in target.id.lower())
        return f"{self.args.target_model_name}_{safe_id}"

    def _target_world_pose(self, target: GatherTargetSpec) -> dict[str, float]:
        anchor_x = float(DEFAULT_MISSION_START_POSE["x"])
        anchor_y = float(DEFAULT_MISSION_START_POSE["y"])
        anchor_yaw = float(DEFAULT_MISSION_START_POSE["yaw"])
        world_x = anchor_x + (math.cos(anchor_yaw) * target.forward_m) - (math.sin(anchor_yaw) * target.lateral_m)
        world_y = anchor_y + (math.sin(anchor_yaw) * target.forward_m) + (math.cos(anchor_yaw) * target.lateral_m)
        return {"x": round(world_x, 6), "y": round(world_y, 6), "z": round(target.z_m, 6)}

    def _truth_state_path(self, session_id: str) -> Path:
        return REPO_ROOT / "artifacts" / "session" / session_id / "visual" / "truth_state.json"

    def _load_truth_state(self, session_id: str) -> dict[str, Any]:
        return read_json(self._truth_state_path(session_id))

    def _wait_for_truth_models(self, session_id: str, expected_names: set[str], timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = self._load_truth_state(session_id)
            target_poses = last_state.get("target_poses_by_name") if isinstance(last_state.get("target_poses_by_name"), dict) else {}
            names_seen = set(str(name) for name in target_poses.keys())
            if expected_names.issubset(names_seen):
                return last_state
            time.sleep(0.5)
        raise RuntimeError(f"Truth probe did not report expected gather models: {sorted(expected_names)}")

    def _ball_truth_pose(self, session_id: str, target: GatherTargetSpec) -> dict[str, float] | None:
        truth_state = self._load_truth_state(session_id)
        target_poses = truth_state.get("target_poses_by_name") if isinstance(truth_state.get("target_poses_by_name"), dict) else {}
        model_pose = target_poses.get(self._target_model_name(target))
        if not isinstance(model_pose, dict):
            return None
        return truth_world_xy(model_pose)

    def _release_sample(
        self,
        *,
        release_started_monotonic: float,
        now_monotonic: float,
        ball_pose: dict[str, Any] | None,
        zone_score: Any,
    ) -> dict[str, Any]:
        sample = {
            "elapsed_s": round(max(float(now_monotonic) - float(release_started_monotonic), 0.0), 6),
            "ball_pose": ball_pose or {},
            "zone_distance_m": 0.0,
            "inside_zone": False,
            "center_inside_zone": False,
        }
        if zone_score is not None:
            sample.update(zone_score.to_dict())
        return sample

    def _final_corral_audit_snapshot(
        self,
        *,
        session_id: str,
        previous_poses: dict[str, dict[str, float] | None] | None = None,
    ) -> dict[str, Any]:
        current_poses: dict[str, dict[str, float] | None] = {}
        final_corral_audit: dict[str, dict[str, Any]] = {}
        for target in self.targets:
            ball_pose = self._ball_truth_pose(session_id, target)
            current_poses[target.id] = dict(ball_pose) if isinstance(ball_pose, dict) else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
            ball_motion_m = pose_delta_m((previous_poses or {}).get(target.id), ball_pose)
            entry: dict[str, Any] = {
                "distance_to_zone_center_m": (
                    round(float(zone_score.retrieval_distance_m), 6) if zone_score is not None else None
                ),
                "inside_retrieval_corral": bool(zone_score and zone_score.center_inside_retrieval_corral),
                "stopped_in_corral": bool(
                    zone_score
                    and zone_score.center_inside_retrieval_corral
                    and ball_motion_m is not None
                    and ball_motion_m <= DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
                ),
            }
            if ball_motion_m is not None:
                entry["ball_motion_m"] = round(float(ball_motion_m), 6)
            final_corral_audit[target.id] = entry
        retrieved_count = sum(1 for entry in final_corral_audit.values() if bool(entry.get("inside_retrieval_corral", False)))
        final_all_targets_inside_retrieval_corral = bool(final_corral_audit) and retrieved_count == len(self.targets)
        latest_all_targets_stopped = bool(final_corral_audit) and all(
            bool(entry.get("inside_retrieval_corral", False)) and bool(entry.get("stopped_in_corral", False))
            for entry in final_corral_audit.values()
        )
        return {
            "final_corral_audit": final_corral_audit,
            "retrieved_count": retrieved_count,
            "final_all_targets_inside_retrieval_corral": final_all_targets_inside_retrieval_corral,
            "latest_all_targets_stopped": latest_all_targets_stopped,
            "current_poses": current_poses,
        }

    def _run_final_corral_audit(self, *, session_id: str, state_history_path: Path) -> dict[str, Any]:
        self._safe_stop()
        self._set_manual_drive(
            False,
            mode="final_corral_audit",
            rationale="Holding the robot still while auditing all placed balls in the retrieval corral.",
        )
        deadline = time.monotonic() + max(
            DEFAULT_RELEASE_SETTLE_MAX_WAIT_S,
            DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S + 1.0,
        )
        stable_started_monotonic: float | None = None
        previous_poses: dict[str, dict[str, float] | None] = {}
        latest_snapshot = self._final_corral_audit_snapshot(session_id=session_id, previous_poses=None)
        latest_snapshot["final_all_targets_stopped"] = False
        latest_snapshot["final_three_ball_corral_pass"] = False
        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            snapshot = self._final_corral_audit_snapshot(
                session_id=session_id,
                previous_poses=previous_poses if previous_poses else None,
            )
            previous_poses = snapshot.pop("current_poses", {})
            all_inside = bool(snapshot.get("final_all_targets_inside_retrieval_corral", False))
            latest_all_targets_stopped = bool(snapshot.get("latest_all_targets_stopped", False))
            if all_inside and latest_all_targets_stopped:
                stable_started_monotonic = (
                    now_monotonic if stable_started_monotonic is None else stable_started_monotonic
                )
            else:
                stable_started_monotonic = None
            stable_window_complete = bool(
                stable_started_monotonic is not None
                and (now_monotonic - stable_started_monotonic) >= DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
            )
            snapshot["final_all_targets_stopped"] = stable_window_complete
            snapshot["final_three_ball_corral_pass"] = stable_window_complete and all_inside
            latest_snapshot = snapshot
            append_jsonl(
                state_history_path,
                {
                    "generated_utc": utc_now(),
                    "phase": "final_corral_audit",
                    "targets": snapshot.get("final_corral_audit", {}),
                    "retrieved_count": int(snapshot.get("retrieved_count", 0) or 0),
                    "final_all_targets_inside_retrieval_corral": bool(snapshot.get("final_all_targets_inside_retrieval_corral", False)),
                    "latest_all_targets_stopped": latest_all_targets_stopped,
                    "stable_window_complete": stable_window_complete,
                    **self._control_debug_fields(),
                },
            )
            self._update_gather_runtime_state(
                mission_phase="final_corral_audit",
                gather_phase="final_corral_audit",
                latest_feedback="Auditing all gathered balls inside the retrieval corral.",
                final_corral_audit=snapshot.get("final_corral_audit", {}),
            )
            if bool(snapshot.get("final_three_ball_corral_pass", False)):
                self._append_runtime_event(
                    "Final three-ball corral audit passed.",
                    category="mission",
                    key=f"final_corral_audit_pass:{session_id}",
                )
                return latest_snapshot
            time.sleep(self.args.poll_s)
        self._append_runtime_event(
            "Final three-ball corral audit timed out before all balls settled inside the retrieval corral.",
            category="warn",
            key=f"final_corral_audit_timeout:{session_id}",
        )
        latest_snapshot["final_all_targets_stopped"] = False
        latest_snapshot["final_three_ball_corral_pass"] = False
        return latest_snapshot

    def _start_motion_bridge(self, compose_project: str, mission_root: Path) -> None:
        gate_stack_container = self._container_id(compose_project, "gate-stack")
        runtime_container_path = to_container_repo_path(self.gather_runtime_state_path)
        log_path = mission_root / "gather_motion_bridge.log"
        script = f"""
set -euo pipefail
PID_FILE="/tmp/chasecar_gather_motion_bridge.pid"
LOG_FILE="/tmp/chasecar_gather_motion_bridge.log"
pkill -f "gather_motion_bridge.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/gather_motion_bridge.py --runtime-json {json.dumps(runtime_container_path)} --loop-rate-hz {json.dumps(str(self.args.motion_loop_hz))}' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
cat "$LOG_FILE" || true
"""
        rc, output = self._docker_exec(gate_stack_container, script)
        log_path.write_text(output + "\n", encoding="utf-8")
        if rc != 0:
            raise RuntimeError(f"Failed to start gather motion bridge: {output}")

    def _stop_motion_bridge(self, compose_project: str) -> None:
        try:
            gate_stack_container = self._container_id(compose_project, "gate-stack")
        except Exception:
            return
        script = """
set +e
if [ -f /tmp/chasecar_gather_motion_bridge.pid ]; then
  PID="$(cat /tmp/chasecar_gather_motion_bridge.pid 2>/dev/null || true)"
  [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
fi
pkill -f "gather_motion_bridge.py" 2>/dev/null || true
"""
        self._docker_exec(gate_stack_container, script)

    def _set_manual_drive(self, enabled: bool, *, linear_x: float = 0.0, angular_z: float = 0.0, mode: str = "idle", rationale: str = "") -> None:
        manual_drive = dict(self.gather_runtime_state.get("manual_drive", {}) or {})
        self._gather_sequence += 1
        manual_drive.update(
            {
                "enabled": bool(enabled),
                "sequence": self._gather_sequence,
                "mode": str(mode),
                "updated_utc": utc_now(),
                "command": {
                    "linear_x": round(float(linear_x), 6),
                    "angular_z": round(float(angular_z), 6),
                },
                "rationale": str(rationale or ""),
            }
        )
        self._update_gather_runtime_state(manual_drive=manual_drive)

    def _record_target_position(self, target_id: str, *, x: float, y: float, z: float = 0.05) -> None:
        target_positions = dict(self.visit_runtime_state.get("target_positions", {}) or {})
        target_positions[str(target_id)] = {
            "x": round(float(x), 6),
            "y": round(float(y), 6),
            "z": round(float(z), 6),
        }
        self._update_visit_runtime_state(target_positions=target_positions)

    def _update_prior_from_ball_pose(self, target_id: str, ball_pose: dict[str, Any] | None) -> None:
        if not ball_pose:
            return
        x = clean_number(ball_pose.get("x"))
        y = clean_number(ball_pose.get("y"))
        z = clean_number(ball_pose.get("z"))
        if x is None or y is None:
            return
        self._update_visit_runtime_state(current_target_prior={"x": round(x, 6), "y": round(y, 6)})
        self._record_target_position(target_id, x=x, y=y, z=z or 0.05)

    def _init_runtime_state(self, *, session_id: str, mission_root: Path) -> None:
        target_positions = {
            target.id: self._target_world_pose(target)
            for target in self.targets
        }
        self.visit_runtime_state = {
            "running": True,
            "scenario_id": str(self.args.scenario_id),
            "session_id": session_id,
            "world_file": self.world_file,
            "surface_profile": self.surface_profile,
            "proof_state": "waiting",
            "mission_phase": "setup",
            "mission_status": "running",
            "current_target_id": "",
            "visit_index": 0,
            "visited_targets": [],
            "remaining_targets": [item.id for item in self.targets],
            "last_visit_result": {},
            "mission_verdict": {},
            "latest_operator_event": "",
            "recent_operator_events": [],
            "latest_feedback": "",
            "current_target_prior": {},
            "target_positions": target_positions,
            "artifact_dir": str(mission_root),
            "updated_utc": utc_now(),
        }
        self.gather_runtime_state = {
            "running": True,
            "scenario_id": str(self.args.scenario_id),
            "session_id": session_id,
            "world_file": self.world_file,
            "surface_profile": self.surface_profile,
            "mission_phase": "setup",
            "mission_status": "running",
            "gather_phase": "setup",
            "current_target_id": "",
            "visit_index": 0,
            "placed_targets": [],
            "remaining_targets": [item.id for item in self.targets],
            "route_order": [],
            "capture_state": {},
            "capture_loss_count": 0,
            "zone_pose": {
                "x": round(self.zone.world_x, 6),
                "y": round(self.zone.world_y, 6),
                "radius_m": round(self.zone.retrieval_radius_m, 6),
                "control_radius_m": round(self.zone.control_radius_m, 6),
                "dwell_s": round(self.zone.dwell_s, 6),
            },
            "zone_score": {},
            "final_corral_audit": {},
            "settle_metrics": {},
            "manual_drive": {
                "enabled": False,
                "sequence": 0,
                "mode": "idle",
                "updated_utc": utc_now(),
                "command": {"linear_x": 0.0, "angular_z": 0.0},
                "rationale": "",
            },
            "latest_control_command": {},
            "latest_feedback": "",
            "mission_verdict": {},
            "latest_operator_event": "",
            "recent_operator_events": [],
            "artifact_dir": str(mission_root),
            "updated_utc": utc_now(),
        }
        self._persist_visit_runtime_state()
        self._persist_gather_runtime_state()

    def _spawn_mission_models(self, ready_state: dict[str, Any], mission_root: Path) -> None:
        compose_project = clean_text(ready_state.get("compose_project"))
        world_name = clean_text(ready_state.get("world_name"), DEFAULT_WORLD_NAME)
        self._set_robot_pose(
            ready_state,
            x=float(DEFAULT_MISSION_START_POSE["x"]),
            y=float(DEFAULT_MISSION_START_POSE["y"]),
            yaw=float(DEFAULT_MISSION_START_POSE["yaw"]),
        )
        self._wait_for_robot_pose_near(
            x=float(DEFAULT_MISSION_START_POSE["x"]),
            y=float(DEFAULT_MISSION_START_POSE["y"]),
            yaw=float(DEFAULT_MISSION_START_POSE["yaw"]),
        )
        self._remove_model(compose_project=compose_project, world_name=world_name, model_name=self.args.zone_model_name)
        self._spawn_model(
            compose_project=compose_project,
            world_name=world_name,
            model_sdf_host=Path(self.args.zone_model_sdf).resolve(),
            model_name=self.args.zone_model_name,
            x=float(self.zone.world_x),
            y=float(self.zone.world_y),
            z=float(self.zone.z_m),
            yaw=0.0,
            log_path=mission_root / "zone_spawn.log",
        )
        for target in self.targets:
            world_pose = self._target_world_pose(target)
            self._spawn_model(
                compose_project=compose_project,
                world_name=world_name,
                model_sdf_host=Path(self.args.target_model_sdf).resolve(),
                model_name=self._target_model_name(target),
                x=float(world_pose["x"]),
                y=float(world_pose["y"]),
                z=float(world_pose["z"]),
                yaw=0.0,
                log_path=mission_root / f"{target.id}_spawn.log",
            )
            self._record_target_position(target.id, x=float(world_pose["x"]), y=float(world_pose["y"]), z=float(world_pose["z"]))

    def _clear_mission_models(self, state: dict[str, Any]) -> None:
        compose_project = clean_text(state.get("compose_project"))
        if not compose_project:
            return
        world_name = clean_text(state.get("world_name"), DEFAULT_WORLD_NAME)
        try:
            self._remove_model(compose_project=compose_project, world_name=world_name, model_name=self.args.zone_model_name)
        except Exception:
            pass
        for target in self.targets:
            try:
                self._remove_model(compose_project=compose_project, world_name=world_name, model_name=self._target_model_name(target))
            except Exception:
                pass

    def _nearest_remaining_route(self, remaining_ids: list[str], state: dict[str, Any]) -> list[str]:
        robot_pose = state.get("belief", {}).get("latest_robot_pose") if isinstance(state.get("belief"), dict) else {}
        robot_xyyaw = world_pose_xyyaw(robot_pose if isinstance(robot_pose, dict) else {})
        if robot_xyyaw is None:
            return list(remaining_ids)
        robot_x, robot_y, _robot_yaw = robot_xyyaw
        ordered = sorted(
            remaining_ids,
            key=lambda target_id: math.hypot(
                float(self._target_world_pose(self.targets_by_id[target_id])["x"]) - robot_x,
                float(self._target_world_pose(self.targets_by_id[target_id])["y"]) - robot_y,
            ),
        )
        return ordered

    def _plan_collection_route(self, remaining_ids: list[str], state: dict[str, Any]) -> list[str]:
        if len(remaining_ids) <= 1:
            return list(remaining_ids)

        enabled, disabled_reason = self.provider.is_enabled()
        if not enabled:
            self._append_runtime_event(
                f"Collection planner unavailable ({disabled_reason}); falling back to nearest target ordering.",
                category="warning",
                key="collection_planner_disabled",
            )
            return self._nearest_remaining_route(remaining_ids, state)

        target_details: list[dict[str, Any]] = []
        robot_pose = state.get("belief", {}).get("latest_robot_pose") if isinstance(state.get("belief"), dict) else {}
        robot_xyyaw = world_pose_xyyaw(robot_pose if isinstance(robot_pose, dict) else {})
        for target_id in remaining_ids:
            target = self.targets_by_id[target_id]
            world_pose = self._target_world_pose(target)
            zone_distance_m = math.hypot(float(world_pose["x"]) - self.zone.world_x, float(world_pose["y"]) - self.zone.world_y)
            entry = {
                "target_id": target.id,
                "label": target.label,
                "world": {"x": world_pose["x"], "y": world_pose["y"]},
                "zone_distance_m": round(zone_distance_m, 6),
                "start_visible": bool(target.start_visible),
            }
            if robot_xyyaw is not None:
                entry["robot_distance_m"] = round(
                    math.hypot(float(world_pose["x"]) - robot_xyyaw[0], float(world_pose["y"]) - robot_xyyaw[1]),
                    6,
                )
            target_details.append(entry)

        try:
            if hasattr(self.provider, "plan_collection_route"):
                ordered = self.provider.plan_collection_route(  # type: ignore[attr-defined]
                    remaining_target_ids=list(remaining_ids),
                    target_details=target_details,
                    zone_details={
                        "world_x": round(self.zone.world_x, 6),
                        "world_y": round(self.zone.world_y, 6),
                        "radius_m": round(self.zone.retrieval_radius_m, 6),
                        "control_radius_m": round(self.zone.control_radius_m, 6),
                    },
                    placed_targets=list(self.gather_runtime_state.get("placed_targets", [])),
                    mission_state={
                        "scenario_id": self.args.scenario_id,
                        "robot_pose": robot_pose if isinstance(robot_pose, dict) else {},
                    },
                    timeout_s=self.args.timeout_s,
                )
            else:
                ordered = self.provider.plan_route(  # type: ignore[attr-defined]
                    remaining_target_ids=list(remaining_ids),
                    target_details=target_details,
                    timeout_s=self.args.timeout_s,
                )
            ordered_ids = [target_id for target_id in ordered if target_id in remaining_ids]
            if set(ordered_ids) != set(remaining_ids):
                raise ProviderError(f"Collection route returned {ordered_ids}, expected exactly {remaining_ids}")
            return ordered_ids
        except Exception as exc:
            self._append_runtime_event(
                f"Collection planner failed ({exc}); falling back to nearest target ordering.",
                category="warning",
                key=f"collection_plan_fallback:{','.join(sorted(remaining_ids))}",
            )
            return self._nearest_remaining_route(remaining_ids, state)

    def _reuse_prior_route_order(self, remaining_ids: list[str], route_decisions: list[dict[str, Any]]) -> list[str]:
        if self.args.scenario_id != "gather_three_ball_zone" or not route_decisions:
            return []
        prior_order = route_decisions[-1].get("ordered_ids", [])
        if not isinstance(prior_order, list):
            return []
        reused = [str(target_id) for target_id in prior_order if target_id in remaining_ids]
        if set(reused) != set(remaining_ids):
            return []
        return reused

    def _dispatch_visit_target(self, target_id: str) -> None:
        deadline = time.monotonic() + 12.0
        last_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            status, payload = dispatch_intent(
                self.dashboard_url,
                "visit_target",
                {"target_id": target_id},
                timeout_s=self.args.timeout_s,
            )
            last_payload = payload
            if status == 202 and bool(payload.get("accepted", False)):
                return
            if "intent already in progress" not in clean_text(payload.get("error")).lower():
                break
            time.sleep(0.5)
        raise RuntimeError(f"visit_target dispatch rejected for {target_id}: {last_payload}")

    def _wait_for_visit_result(
        self,
        *,
        timeout_s: float,
        baseline_status: str,
        baseline_feedback: str,
        target_id: str,
    ) -> tuple[bool, dict[str, Any], str]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            brain = last_state.get("brain", {}) if isinstance(last_state.get("brain"), dict) else {}
            status = clean_text(brain.get("last_feedback_status"))
            feedback = clean_text(brain.get("last_feedback_text") or last_state.get("last_feedback"))
            self._update_gather_runtime_state(latest_feedback=feedback)
            self._update_visit_runtime_state(latest_feedback=feedback)
            if status == baseline_status and feedback == baseline_feedback:
                time.sleep(self.args.poll_s)
                continue
            if status == "visit_target_reached" or feedback.lower() == f"visit_target: {target_id.lower()} reached":
                return True, last_state, status
            if status == "visit_target_failed" or (feedback.lower().startswith(f"visit_target: {target_id.lower()} failed")):
                return False, last_state, status
            time.sleep(self.args.poll_s)
        return False, last_state, "visit_target_timeout"

    def _control_loop_state(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, float] | None]:
        dashboard_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
        robot_pose = dashboard_state.get("belief", {}).get("latest_robot_pose") if isinstance(dashboard_state.get("belief"), dict) else {}
        robot_world = robot_pose if isinstance(robot_pose, dict) else {}
        ball_pose = self._ball_truth_pose(session_id, target)
        return dashboard_state, robot_world, ball_pose

    def _pre_stage_target(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
        state_history_path: Path,
        mission_root: Path,
        attempt_index: int = 0,
        attempt_kind: str = "",
    ) -> tuple[bool, dict[str, Any]]:
        pre_stage_timeout_s = DEFAULT_PRE_STAGE_TIMEOUT_S
        if self.gather_control_family == NAV2_MPPI_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY:
            pre_stage_timeout_s = max(
                pre_stage_timeout_s,
                DEFAULT_NAV2_MPPI_FOLLOW_PATH_PRE_STAGE_TIMEOUT_S,
            )
        if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
            pre_stage_timeout_s = max(
                pre_stage_timeout_s,
                DEFAULT_OBJECT_CENTRIC_PRE_STAGE_TIMEOUT_S,
            )
            if self.mission_objective == MISSION_OBJECTIVE_FETCH_TO_POSE:
                pre_stage_timeout_s = max(
                    pre_stage_timeout_s,
                    DEFAULT_OBJECT_CENTRIC_FETCH_PRE_STAGE_TIMEOUT_S,
                )
        deadline = time.monotonic() + max(pre_stage_timeout_s, 0.1)
        pre_stage_started_monotonic = time.monotonic()
        pre_stage_ready_started_monotonic: float | None = None
        pre_stage_pose_reached_once = False
        pre_stage_pose_world: dict[str, Any] = {}
        push_direction_yaw_deg = 0.0
        last_failure_reason = ""
        latest_pre_capture_command_mode = ""
        short_horizon_strategy_name = ""
        short_horizon_objective_name = ""
        short_horizon_best_progress_score: float | None = None
        short_horizon_last_progress_monotonic = pre_stage_started_monotonic
        short_horizon_strategy_started_monotonic = pre_stage_started_monotonic
        nav2_reacquire_attempted = False
        nav2_follow_path_reacquire_attempted = False
        constrained_local_previous_ball_pose: dict[str, Any] | None = None
        docking_reacquire_previous_ball_pose: dict[str, Any] | None = None
        handoff_yaw_servo_previous_ball_pose: dict[str, Any] | None = None
        pre_stage_reacquire_fsm_previous_ball_pose: dict[str, Any] | None = None
        pre_stage_path_tracker_previous_ball_pose: dict[str, Any] | None = None
        pre_stage_path_tracker_waypoint_index = 0
        pre_stage_trajectory_owner_previous_ball_pose: dict[str, Any] | None = None
        pre_stage_trajectory_owner_milestone_index = 0
        pre_stage_trajectory_owner_side_sign: float | None = None
        pre_stage_trajectory_owner_replan_count = 0
        object_centric_previous_command: PlaceControlCommand | None = None
        object_centric_previous_ball_pose: dict[str, Any] | None = None
        last_object_centric_policy: dict[str, Any] = {}

        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            _dashboard_state, robot_pose, ball_pose = self._control_loop_state(session_id=session_id, target=target)
            capture = capture_snapshot(robot_pose, ball_pose or {}, self.capture_envelope) if robot_pose and ball_pose else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
            pre_stage_snapshot = (
                pre_stage_arrival_snapshot(robot_pose, ball_pose or {}, zone=self.zone)
                if robot_pose and ball_pose
                else None
            )
            pre_stage_command = (
                compute_pre_stage_command(robot_pose, ball_pose or {}, zone=self.zone)
                if robot_pose and ball_pose
                else None
            )
            pre_stage_strategy_name = ""
            pre_stage_objective_name = ""
            pre_stage_progress_score: float | None = None
            pre_stage_stall_s: float | None = None
            pre_stage_projected_projection_gain: float | None = None
            pre_stage_projected_lateral_gain: float | None = None
            pre_stage_projected_distance_gain: float | None = None
            constrained_local_debug_fields: dict[str, Any] = {}
            docking_reacquire_debug_fields: dict[str, Any] = {}
            handoff_yaw_servo_debug_fields: dict[str, Any] = {}
            pre_stage_reacquire_fsm_debug_fields: dict[str, Any] = {}
            pre_stage_path_tracker_debug_fields: dict[str, Any] = {}
            pre_stage_trajectory_owner_debug_fields: dict[str, Any] = {}
            object_centric_debug_fields: dict[str, Any] = {}
            pre_stage_reacquire_fsm_abort_reason = ""
            pre_stage_path_tracker_abort_reason = ""
            pre_stage_trajectory_owner_abort_reason = ""
            pre_stage_ready_signal = False
            constrained_local_ball_motion_m = (
                pose_delta_m(constrained_local_previous_ball_pose, ball_pose)
                if constrained_local_previous_ball_pose is not None and ball_pose
                else None
            )
            docking_reacquire_ball_motion_m = (
                pose_delta_m(docking_reacquire_previous_ball_pose, ball_pose)
                if docking_reacquire_previous_ball_pose is not None and ball_pose
                else None
            )
            handoff_yaw_servo_ball_motion_m = (
                pose_delta_m(handoff_yaw_servo_previous_ball_pose, ball_pose)
                if handoff_yaw_servo_previous_ball_pose is not None and ball_pose
                else None
            )
            pre_stage_reacquire_fsm_ball_motion_m = (
                pose_delta_m(pre_stage_reacquire_fsm_previous_ball_pose, ball_pose)
                if pre_stage_reacquire_fsm_previous_ball_pose is not None and ball_pose
                else None
            )
            pre_stage_path_tracker_ball_motion_m = (
                pose_delta_m(pre_stage_path_tracker_previous_ball_pose, ball_pose)
                if pre_stage_path_tracker_previous_ball_pose is not None and ball_pose
                else None
            )
            pre_stage_trajectory_owner_ball_motion_m = (
                pose_delta_m(pre_stage_trajectory_owner_previous_ball_pose, ball_pose)
                if pre_stage_trajectory_owner_previous_ball_pose is not None and ball_pose
                else None
            )
            if (
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and robot_pose
                and ball_pose
            ):
                object_decision = decide_object_centric_gather_command(
                    robot_pose,
                    ball_pose or {},
                    phase="pre_stage",
                    zone=self.zone,
                    envelope=self.capture_envelope,
                    previous_command=object_centric_previous_command,
                    previous_ball_pose=object_centric_previous_ball_pose,
                )
                last_object_centric_policy = dict(object_decision.diagnostics)
                object_centric_debug_fields = {"object_centric_policy": last_object_centric_policy}
                if object_decision.command is not None:
                    pre_stage_command = object_decision.command
                    pre_stage_strategy_name = str(object_decision.strategy_name or "")
                    pre_stage_objective_name = str(object_decision.objective_name or "")
                    pre_stage_progress_score = clean_number(object_decision.progress_score)
            if isinstance(pre_stage_snapshot, dict):
                pre_stage_pose_world = (
                    dict(pre_stage_snapshot.get("pre_stage_pose_world", {}))
                    if isinstance(pre_stage_snapshot.get("pre_stage_pose_world"), dict)
                    else {}
                )
                push_direction_yaw_deg = float(clean_number(pre_stage_snapshot.get("push_direction_yaw_deg")) or 0.0)
                pre_stage_ready_signal = bool(pre_stage_snapshot.get("pre_stage_pose_reached", False))
                if pre_stage_ready_signal:
                    pre_stage_pose_reached_once = True
                    pre_stage_ready_started_monotonic = (
                        now_monotonic
                        if pre_stage_ready_started_monotonic is None
                        else pre_stage_ready_started_monotonic
                    )
                else:
                    pre_stage_ready_started_monotonic = None
                if bool(pre_stage_snapshot.get("entered_goal_side_before_capture", False)):
                    last_failure_reason = "entered_goal_side_before_capture"
            if (
                self.gather_control_family == NAV2_REACQUIRE_CONTROL_FAMILY
                and not nav2_reacquire_attempted
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                nav2_plan = compute_nav2_reacquire_pre_stage_goal(
                    robot_pose,
                    ball_pose or {},
                    pre_stage_snapshot,
                )
                if bool(nav2_plan.get("active", False)):
                    nav2_reacquire_attempted = True
                    goal_pose = (
                        dict(nav2_plan.get("goal_pose", {}))
                        if isinstance(nav2_plan.get("goal_pose"), dict)
                        else {}
                    )
                    trigger = (
                        dict(nav2_plan.get("trigger", {}))
                        if isinstance(nav2_plan.get("trigger"), dict)
                        else {}
                    )
                    compose_project = clean_text(_dashboard_state.get("compose_project"))
                    self._set_manual_drive(
                        enabled=False,
                        mode="nav2_reacquire_goal",
                        rationale="Nav2 owns the coarse behind-ball reacquire waypoint for this pre-stage slice.",
                    )
                    self._update_gather_runtime_state(
                        latest_feedback=f"Nav2 reacquiring the behind-ball pre-stage pose for {target.label}.",
                        latest_control_command={
                            "mode": "nav2_reacquire_goal",
                            "linear_x": 0.0,
                            "angular_z": 0.0,
                            "target_speed_scale": 0.0,
                            "rationale": "Manual gather drive disabled while Nav2 owns the pre-stage reacquire waypoint.",
                        },
                    )
                    append_jsonl(
                        state_history_path,
                        {
                            "generated_utc": utc_now(),
                            "phase": "pre_stage",
                            "event_type": "nav2_reacquire_dispatch",
                            "attempt": int(attempt_index),
                            "attempt_kind": str(attempt_kind),
                            "target_id": target.id,
                            "robot_pose": robot_pose,
                            "ball_pose": ball_pose,
                            "pre_stage": pre_stage_snapshot or {},
                            "pre_stage_at_dispatch": pre_stage_snapshot or {},
                            "nav2_goal_pose": goal_pose,
                            "nav2_reacquire_trigger": trigger,
                            "nav2_dispatch_status": "planned",
                            "selected_command": {},
                            **self._control_debug_fields(
                                strategy_name="nav2_reacquire",
                                objective_name=clean_text(goal_pose.get("kind"), "pre_stage_waypoint"),
                            ),
                        },
                    )
                    remaining_timeout_s = max(0.1, deadline - time.monotonic())
                    nav2_timeout_s = min(DEFAULT_NAV2_REACQUIRE_GOAL_TIMEOUT_S, remaining_timeout_s)
                    if compose_project:
                        try:
                            nav2_result = self._dispatch_nav2_reacquire_goal(
                                compose_project=compose_project,
                                goal_pose=goal_pose,
                                timeout_s=nav2_timeout_s,
                            )
                        except Exception as exc:
                            nav2_result = {
                                "dispatch_status": "client_error",
                                "accepted": False,
                                "success": False,
                                "status_code": None,
                                "elapsed_s": 0.0,
                                "error": str(exc),
                            }
                    else:
                        nav2_result = {
                            "dispatch_status": "missing_compose_project",
                            "accepted": False,
                            "success": False,
                            "status_code": None,
                            "elapsed_s": 0.0,
                            "error": "dashboard_state_missing_compose_project",
                        }
                    completion_dashboard_state, completion_robot_pose, completion_ball_pose = self._control_loop_state(
                        session_id=session_id,
                        target=target,
                    )
                    _ = completion_dashboard_state
                    completion_snapshot = (
                        pre_stage_arrival_snapshot(completion_robot_pose, completion_ball_pose or {}, zone=self.zone)
                        if completion_robot_pose and completion_ball_pose
                        else None
                    )
                    append_jsonl(
                        state_history_path,
                        {
                            "generated_utc": utc_now(),
                            "phase": "pre_stage",
                            "event_type": "nav2_reacquire_complete",
                            "attempt": int(attempt_index),
                            "attempt_kind": str(attempt_kind),
                            "target_id": target.id,
                            "robot_pose": completion_robot_pose,
                            "ball_pose": completion_ball_pose,
                            "pre_stage": completion_snapshot or {},
                            "pre_stage_at_dispatch": pre_stage_snapshot or {},
                            "pre_stage_at_completion": completion_snapshot or {},
                            "nav2_goal_pose": goal_pose,
                            "nav2_reacquire_trigger": trigger,
                            "nav2_dispatch_status": clean_text(nav2_result.get("dispatch_status"), "unknown"),
                            "nav2_result": nav2_result,
                            "selected_command": {},
                            **self._control_debug_fields(
                                strategy_name="nav2_reacquire",
                                objective_name=clean_text(goal_pose.get("kind"), "pre_stage_waypoint"),
                            ),
                        },
                    )
                    if not bool(nav2_result.get("success", False)):
                        pre_stage_time_s = time.monotonic() - pre_stage_started_monotonic
                        failure_reason = (
                            "nav2_reacquire_timeout"
                            if clean_text(nav2_result.get("dispatch_status")) == "goal_result_timeout"
                            else "nav2_reacquire_failed"
                        )
                        self._set_manual_drive(
                            enabled=False,
                            mode=failure_reason,
                            rationale="Nav2 pre-stage reacquire did not complete; stopping before baseline gather resumes.",
                        )
                        failure_payload = {
                            "failure_reason": failure_reason,
                            "failure_stage": "pre_stage",
                            "pre_stage_pose_world": pre_stage_pose_world,
                            "pre_stage_pose_reached": bool(pre_stage_pose_reached_once),
                            "pre_stage_time_s": round(pre_stage_time_s, 6),
                            "pre_stage_handoff_pass": False,
                            "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                            "approach_failure_reason": last_failure_reason,
                            "entered_goal_side_before_capture": last_failure_reason == "entered_goal_side_before_capture",
                            "nav2_reacquire_goal_pose": goal_pose,
                            "nav2_reacquire_result": nav2_result,
                        }
                        write_json(mission_root / f"{target.id}_{failure_reason}.json", failure_payload)
                        return False, failure_payload
                    self._set_manual_drive(
                        enabled=False,
                        mode="nav2_reacquire_complete",
                        rationale="Nav2 pre-stage reacquire completed; returning control to baseline gather staging.",
                    )
                    time.sleep(self.args.poll_s)
                    continue
            if (
                self.gather_control_family
                in {
                    NAV2_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY,
                    NAV2_MPPI_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY,
                }
                and not nav2_follow_path_reacquire_attempted
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                mppi_follow_path = self.gather_control_family == NAV2_MPPI_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY
                follow_path_controller_id = (
                    DEFAULT_NAV2_MPPI_FOLLOW_PATH_CONTROLLER_ID
                    if mppi_follow_path
                    else DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_ID
                )
                follow_path_objective_name = (
                    NAV2_MPPI_FOLLOW_PATH_REACQUIRE_OBJECTIVE
                    if mppi_follow_path
                    else NAV2_FOLLOW_PATH_REACQUIRE_OBJECTIVE
                )
                follow_path_display_name = "Nav2 MPPI FollowPath" if mppi_follow_path else "Nav2 FollowPath"
                if mppi_follow_path:
                    follow_path_plan = build_nav2_mppi_follow_path_reacquire_plan(
                        robot_pose,
                        ball_pose or {},
                        zone=self.zone,
                        snapshot=pre_stage_snapshot,
                    )
                else:
                    follow_path_plan = build_nav2_follow_path_reacquire_plan(
                        robot_pose,
                        ball_pose or {},
                        zone=self.zone,
                        snapshot=pre_stage_snapshot,
                    )
                follow_path_plan_dict = follow_path_plan.to_dict()
                follow_path_reason = clean_text(follow_path_plan_dict.get("reason"))
                if (
                    not bool(follow_path_plan_dict.get("active", False))
                    and follow_path_reason
                    and follow_path_reason != "pre_stage_handoff_already_ready"
                ):
                    nav2_follow_path_reacquire_attempted = True
                    failure_reason = (
                        "nav2_follow_path_path_clearance_guard"
                        if follow_path_reason == "follow_path_clearance_guard"
                        else "nav2_follow_path_path_unavailable"
                    )
                    pre_stage_time_s = time.monotonic() - pre_stage_started_monotonic
                    self._set_manual_drive(
                        enabled=False,
                        mode=failure_reason,
                        rationale=f"{follow_path_display_name} pre-stage reacquire could not build a safe path.",
                    )
                    failure_payload = {
                        "failure_reason": failure_reason,
                        "failure_stage": "pre_stage",
                        "pre_stage_pose_world": pre_stage_pose_world,
                        "pre_stage_pose_reached": bool(pre_stage_pose_reached_once),
                        "pre_stage_time_s": round(pre_stage_time_s, 6),
                        "pre_stage_handoff_pass": False,
                        "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                        "approach_failure_reason": last_failure_reason,
                        "entered_goal_side_before_capture": last_failure_reason == "entered_goal_side_before_capture",
                        "nav2_follow_path_plan": follow_path_plan_dict,
                    }
                    append_jsonl(
                        state_history_path,
                        {
                            "generated_utc": utc_now(),
                            "phase": "pre_stage",
                            "event_type": "nav2_follow_path_reacquire_plan_blocked",
                            "attempt": int(attempt_index),
                            "attempt_kind": str(attempt_kind),
                            "target_id": target.id,
                            "robot_pose": robot_pose,
                            "ball_pose": ball_pose,
                            "pre_stage": pre_stage_snapshot or {},
                            "nav2_follow_path_plan": follow_path_plan_dict,
                            "nav2_follow_path_dispatch_status": follow_path_reason or failure_reason,
                            "selected_command": {},
                            **self._control_debug_fields(
                                strategy_name=follow_path_objective_name,
                                objective_name="follow_path_pre_stage_path",
                            ),
                        },
                    )
                    write_json(mission_root / f"{target.id}_{failure_reason}.json", failure_payload)
                    return False, failure_payload
                if bool(follow_path_plan_dict.get("active", False)):
                    nav2_follow_path_reacquire_attempted = True
                    path_poses = [
                        dict(item)
                        for item in follow_path_plan_dict.get("path_poses", [])
                        if isinstance(item, dict)
                    ]
                    compose_project = clean_text(_dashboard_state.get("compose_project"))
                    self._set_manual_drive(
                        enabled=False,
                        mode="nav2_follow_path_reacquire_path",
                        rationale=f"{follow_path_display_name} owns the explicit pre-stage reacquire path.",
                    )
                    self._update_gather_runtime_state(
                        latest_feedback=(
                            f"{follow_path_display_name} is reacquiring the behind-ball pre-stage pose for "
                            f"{target.label}."
                        ),
                        latest_control_command={
                            "mode": "nav2_follow_path_reacquire_path",
                            "linear_x": 0.0,
                            "angular_z": 0.0,
                            "target_speed_scale": 0.0,
                            "rationale": (
                                f"Manual gather drive disabled while {follow_path_display_name} owns "
                                "pre-stage reacquire."
                            ),
                        },
                    )
                    append_jsonl(
                        state_history_path,
                        {
                            "generated_utc": utc_now(),
                            "phase": "pre_stage",
                            "event_type": "nav2_follow_path_reacquire_dispatch",
                            "attempt": int(attempt_index),
                            "attempt_kind": str(attempt_kind),
                            "target_id": target.id,
                            "robot_pose": robot_pose,
                            "ball_pose": ball_pose,
                            "pre_stage": pre_stage_snapshot or {},
                            "pre_stage_at_dispatch": pre_stage_snapshot or {},
                            "nav2_follow_path_plan": follow_path_plan_dict,
                            "nav2_follow_path_path_poses": path_poses,
                            "nav2_follow_path_controller_id": clean_text(
                                follow_path_plan_dict.get("controller_id"),
                                follow_path_controller_id,
                            ),
                            "nav2_follow_path_goal_checker_id": clean_text(
                                follow_path_plan_dict.get("goal_checker_id"),
                                DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID,
                            ),
                            "nav2_follow_path_dispatch_status": "planned",
                            "selected_command": {},
                            **self._control_debug_fields(
                                strategy_name=follow_path_objective_name,
                                objective_name="follow_path_pre_stage_path",
                            ),
                        },
                    )
                    remaining_timeout_s = max(0.1, deadline - time.monotonic())
                    follow_path_timeout_cap_s = (
                        DEFAULT_NAV2_MPPI_FOLLOW_PATH_GOAL_TIMEOUT_S
                        if mppi_follow_path
                        else DEFAULT_NAV2_FOLLOW_PATH_GOAL_TIMEOUT_S
                    )
                    follow_path_timeout_s = min(follow_path_timeout_cap_s, remaining_timeout_s)
                    if compose_project:
                        try:
                            follow_path_result = self._dispatch_nav2_follow_path_reacquire(
                                compose_project=compose_project,
                                path_poses=path_poses,
                                controller_id=clean_text(
                                    follow_path_plan_dict.get("controller_id"),
                                    follow_path_controller_id,
                                ),
                                goal_checker_id=clean_text(
                                    follow_path_plan_dict.get("goal_checker_id"),
                                    DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID,
                                ),
                                timeout_s=follow_path_timeout_s,
                            )
                        except Exception as exc:
                            follow_path_result = {
                                "dispatch_status": "client_error",
                                "accepted": False,
                                "success": False,
                                "status_code": None,
                                "elapsed_s": 0.0,
                                "error": str(exc),
                            }
                    else:
                        follow_path_result = {
                            "dispatch_status": "missing_compose_project",
                            "accepted": False,
                            "success": False,
                            "status_code": None,
                            "elapsed_s": 0.0,
                            "error": "dashboard_state_missing_compose_project",
                        }
                    completion_dashboard_state, completion_robot_pose, completion_ball_pose = self._control_loop_state(
                        session_id=session_id,
                        target=target,
                    )
                    _ = completion_dashboard_state
                    completion_snapshot = (
                        pre_stage_arrival_snapshot(completion_robot_pose, completion_ball_pose or {}, zone=self.zone)
                        if completion_robot_pose and completion_ball_pose
                        else None
                    )
                    follow_path_ball_motion_m = (
                        pose_delta_m(ball_pose, completion_ball_pose)
                        if ball_pose and completion_ball_pose
                        else None
                    )
                    completion_ball_clearance_m = None
                    completion_robot_xyyaw = world_pose_xyyaw(completion_robot_pose or {})
                    completion_ball_xyyaw = world_pose_xyyaw(completion_ball_pose or {})
                    if completion_robot_xyyaw is not None and completion_ball_xyyaw is not None:
                        completion_ball_clearance_m = round(
                            math.hypot(
                                completion_robot_xyyaw[0] - completion_ball_xyyaw[0],
                                completion_robot_xyyaw[1] - completion_ball_xyyaw[1],
                            ),
                            6,
                        )
                    completion_handoff_ready = bool(
                        completion_snapshot.get("pre_stage_pose_reached", False)
                    ) if isinstance(completion_snapshot, dict) else False
                    terminal_path_pose = path_poses[-1] if path_poses else {}
                    dispatch_terminal_path_distance_m = pose_to_path_distance_m(robot_pose, terminal_path_pose)
                    completion_terminal_path_distance_m = pose_to_path_distance_m(
                        completion_robot_pose,
                        terminal_path_pose,
                    )
                    dispatch_terminal_yaw_error_deg = pose_to_path_yaw_error_deg(robot_pose, terminal_path_pose)
                    completion_terminal_yaw_error_deg = pose_to_path_yaw_error_deg(
                        completion_robot_pose,
                        terminal_path_pose,
                    )
                    dispatch_pre_stage_distance_m = pre_stage_snapshot_number(
                        pre_stage_snapshot,
                        "pre_stage_pose_distance_m",
                    )
                    completion_pre_stage_distance_m = pre_stage_snapshot_number(
                        completion_snapshot,
                        "pre_stage_pose_distance_m",
                    )
                    dispatch_lateral_error_m = pre_stage_snapshot_number(
                        pre_stage_snapshot,
                        "robot_lateral_error_m",
                    )
                    completion_lateral_error_m = pre_stage_snapshot_number(
                        completion_snapshot,
                        "robot_lateral_error_m",
                    )
                    dispatch_yaw_error_deg = pre_stage_snapshot_number(pre_stage_snapshot, "yaw_error_deg")
                    completion_yaw_error_deg = pre_stage_snapshot_number(completion_snapshot, "yaw_error_deg")
                    follow_path_robot_motion_m = pose_delta_m(robot_pose, completion_robot_pose)
                    follow_path_diagnostics = {
                        "controller_id": clean_text(
                            follow_path_plan_dict.get("controller_id"),
                            follow_path_controller_id,
                        ),
                        "goal_checker_id": clean_text(
                            follow_path_plan_dict.get("goal_checker_id"),
                            DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID,
                        ),
                        "path_pose_count": len(path_poses),
                        "feedback_count": int(clean_number(follow_path_result.get("feedback_count")) or 0),
                        "feedback_samples": follow_path_result.get("feedback_samples", []),
                        "feedback_last": follow_path_result.get("feedback_last", {}),
                        "dispatch_status": clean_text(follow_path_result.get("dispatch_status"), "unknown"),
                        "success": bool(follow_path_result.get("success", False)),
                        "status_code": clean_number(follow_path_result.get("status_code")),
                        "status_text": clean_text(follow_path_result.get("status_text")),
                        "error": clean_text(follow_path_result.get("error")),
                        "action_result": follow_path_result.get("action_result", {}),
                        "timeout_s": clean_rounded_number(follow_path_result.get("timeout_s")),
                        "elapsed_s": clean_rounded_number(follow_path_result.get("elapsed_s")),
                        "timed_out": bool(follow_path_result.get("timed_out", False)),
                        "cancel_requested": bool(follow_path_result.get("cancel_requested", False)),
                        "cancel_response_received": bool(
                            follow_path_result.get("cancel_response_received", False)
                        ),
                        "cancel_goal_count": int(clean_number(follow_path_result.get("cancel_goal_count")) or 0),
                        "cancel_elapsed_s": clean_rounded_number(follow_path_result.get("cancel_elapsed_s")),
                        "controller_log_excerpt": follow_path_result.get("controller_log_excerpt", {}),
                        "cmd_vel_counts": follow_path_result.get("cmd_vel_counts", {}),
                        "cmd_vel_samples": follow_path_result.get("cmd_vel_samples", []),
                        "cmd_vel_last": follow_path_result.get("cmd_vel_last", {}),
                        "odom_count": int(clean_number(follow_path_result.get("odom_count")) or 0),
                        "odom_samples": follow_path_result.get("odom_samples", []),
                        "odom_last": follow_path_result.get("odom_last", {}),
                        "odom_delta": follow_path_result.get("odom_delta", {}),
                        "path_progress_samples": follow_path_result.get("path_progress_samples", []),
                        "path_progress_last": follow_path_result.get("path_progress_last", {}),
                        "dispatch_terminal_path_distance_m": clean_rounded_number(
                            dispatch_terminal_path_distance_m
                        ),
                        "completion_terminal_path_distance_m": clean_rounded_number(
                            completion_terminal_path_distance_m
                        ),
                        "terminal_path_distance_reduction_m": numeric_reduction(
                            dispatch_terminal_path_distance_m,
                            completion_terminal_path_distance_m,
                        ),
                        "dispatch_terminal_yaw_error_deg": clean_rounded_number(
                            dispatch_terminal_yaw_error_deg
                        ),
                        "completion_terminal_yaw_error_deg": clean_rounded_number(
                            completion_terminal_yaw_error_deg
                        ),
                        "dispatch_pre_stage_distance_m": dispatch_pre_stage_distance_m,
                        "completion_pre_stage_distance_m": completion_pre_stage_distance_m,
                        "pre_stage_distance_reduction_m": numeric_reduction(
                            dispatch_pre_stage_distance_m,
                            completion_pre_stage_distance_m,
                        ),
                        "dispatch_lateral_error_m": dispatch_lateral_error_m,
                        "completion_lateral_error_m": completion_lateral_error_m,
                        "lateral_error_reduction_m": numeric_reduction(
                            dispatch_lateral_error_m,
                            completion_lateral_error_m,
                        ),
                        "dispatch_yaw_error_deg": dispatch_yaw_error_deg,
                        "completion_yaw_error_deg": completion_yaw_error_deg,
                        "yaw_error_reduction_deg": numeric_reduction(
                            dispatch_yaw_error_deg,
                            completion_yaw_error_deg,
                        ),
                        "robot_motion_m": clean_rounded_number(follow_path_robot_motion_m),
                        "ball_motion_m": clean_rounded_number(follow_path_ball_motion_m),
                        "completion_ball_clearance_m": clean_rounded_number(completion_ball_clearance_m),
                        "min_plan_ball_clearance_m": clean_rounded_number(
                            follow_path_plan_dict.get("min_path_ball_clearance_m")
                        ),
                        "measured_handoff_ready": bool(completion_handoff_ready),
                    }
                    append_jsonl(
                        state_history_path,
                        {
                            "generated_utc": utc_now(),
                            "phase": "pre_stage",
                            "event_type": "nav2_follow_path_reacquire_complete",
                            "attempt": int(attempt_index),
                            "attempt_kind": str(attempt_kind),
                            "target_id": target.id,
                            "robot_pose": completion_robot_pose,
                            "ball_pose": completion_ball_pose,
                            "pre_stage": completion_snapshot or {},
                            "pre_stage_at_dispatch": pre_stage_snapshot or {},
                            "pre_stage_at_completion": completion_snapshot or {},
                            "nav2_follow_path_plan": follow_path_plan_dict,
                            "nav2_follow_path_path_poses": path_poses,
                            "nav2_follow_path_dispatch_status": clean_text(
                                follow_path_result.get("dispatch_status"),
                                "unknown",
                            ),
                            "nav2_follow_path_result": follow_path_result,
                            "nav2_follow_path_ball_motion_m": clean_number(follow_path_ball_motion_m),
                            "nav2_follow_path_robot_motion_m": clean_number(follow_path_robot_motion_m),
                            "nav2_follow_path_min_ball_clearance_m": clean_number(
                                follow_path_plan_dict.get("min_path_ball_clearance_m")
                            ),
                            "nav2_follow_path_completion_ball_clearance_m": clean_number(
                                completion_ball_clearance_m
                            ),
                            "nav2_follow_path_terminal_path_distance_m": clean_number(
                                completion_terminal_path_distance_m
                            ),
                            "nav2_follow_path_terminal_yaw_error_deg": clean_number(
                                completion_terminal_yaw_error_deg
                            ),
                            "nav2_follow_path_feedback_count": int(
                                clean_number(follow_path_result.get("feedback_count")) or 0
                            ),
                            "nav2_follow_path_feedback_samples": follow_path_result.get("feedback_samples", []),
                            "nav2_follow_path_diagnostics": follow_path_diagnostics,
                            "nav2_follow_path_measured_handoff_ready": completion_handoff_ready,
                            "selected_command": {},
                            **self._control_debug_fields(
                                strategy_name=follow_path_objective_name,
                                objective_name="follow_path_pre_stage_path",
                            ),
                        },
                    )
                    failure_reason = ""
                    if not bool(follow_path_result.get("success", False)):
                        failure_reason = (
                            "nav2_follow_path_timeout"
                            if clean_text(follow_path_result.get("dispatch_status")) == "goal_result_timeout"
                            else "nav2_follow_path_failed"
                        )
                    elif (
                        follow_path_ball_motion_m is not None
                        and float(follow_path_ball_motion_m) > DEFAULT_NAV2_FOLLOW_PATH_BALL_MOTION_TOLERANCE_M
                    ):
                        failure_reason = "nav2_follow_path_ball_motion_guard"
                    elif not completion_handoff_ready:
                        failure_reason = "nav2_follow_path_post_action_not_handoff_ready"
                    if failure_reason:
                        pre_stage_time_s = time.monotonic() - pre_stage_started_monotonic
                        self._set_manual_drive(
                            enabled=False,
                            mode=failure_reason,
                            rationale=f"{follow_path_display_name} pre-stage reacquire stopped before measured handoff.",
                        )
                        failure_payload = {
                            "failure_reason": failure_reason,
                            "failure_stage": "pre_stage",
                            "pre_stage_pose_world": pre_stage_pose_world,
                            "pre_stage_pose_reached": bool(pre_stage_pose_reached_once or completion_handoff_ready),
                            "pre_stage_time_s": round(pre_stage_time_s, 6),
                            "pre_stage_handoff_pass": False,
                            "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                            "approach_failure_reason": (
                                last_failure_reason
                                if last_failure_reason
                                else (
                                    "ball_motion_guard"
                                    if failure_reason == "nav2_follow_path_ball_motion_guard"
                                    else failure_reason
                                )
                            ),
                            "entered_goal_side_before_capture": last_failure_reason == "entered_goal_side_before_capture",
                            "nav2_follow_path_plan": follow_path_plan_dict,
                            "nav2_follow_path_result": follow_path_result,
                            "nav2_follow_path_diagnostics": follow_path_diagnostics,
                            "nav2_follow_path_ball_motion_m": clean_number(follow_path_ball_motion_m),
                            "nav2_follow_path_robot_motion_m": clean_number(follow_path_robot_motion_m),
                            "pre_stage_at_completion": completion_snapshot or {},
                        }
                        write_json(mission_root / f"{target.id}_{failure_reason}.json", failure_payload)
                        return False, failure_payload
                    self._set_manual_drive(
                        enabled=False,
                        mode="nav2_follow_path_reacquire_complete",
                        rationale=(
                            f"{follow_path_display_name} pre-stage reacquire completed; "
                            "waiting for measured handoff dwell."
                        ),
                    )
                    time.sleep(self.args.poll_s)
                    continue
            if (
                self.gather_control_family in {"short_horizon_v1", "short_horizon_v2"}
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                decision = decide_short_horizon_pre_stage_command(
                    robot_pose,
                    ball_pose or {},
                    zone=self.zone,
                    snapshot=pre_stage_snapshot,
                    control_family=self.gather_control_family,
                    previous_strategy_name=short_horizon_strategy_name,
                    stall_s=max(0.0, now_monotonic - short_horizon_last_progress_monotonic),
                    strategy_elapsed_s=max(0.0, now_monotonic - short_horizon_strategy_started_monotonic),
                )
                if decision.active and decision.command is not None:
                    pre_stage_command = decision.command
                    pre_stage_strategy_name = str(decision.strategy_name or "")
                    pre_stage_objective_name = str(decision.objective_name or "")
                    pre_stage_progress_score = (
                        float(decision.progress_score)
                        if decision.progress_score is not None
                        else None
                    )
                    if decision.projection is not None:
                        pre_stage_projected_projection_gain = float(decision.projection.projected_projection_gain)
                        pre_stage_projected_lateral_gain = float(decision.projection.projected_lateral_gain)
                        pre_stage_projected_distance_gain = float(decision.projection.projected_distance_gain)
                    if (
                        pre_stage_progress_score is not None
                        and (
                            short_horizon_best_progress_score is None
                            or pre_stage_progress_score > short_horizon_best_progress_score + 1.0e-6
                        )
                    ):
                        short_horizon_best_progress_score = pre_stage_progress_score
                        short_horizon_last_progress_monotonic = now_monotonic
                    pre_stage_stall_s = max(0.0, now_monotonic - short_horizon_last_progress_monotonic)
                    if pre_stage_strategy_name != short_horizon_strategy_name:
                        short_horizon_strategy_started_monotonic = now_monotonic
                    short_horizon_strategy_name = pre_stage_strategy_name
                    short_horizon_objective_name = pre_stage_objective_name
                else:
                    short_horizon_strategy_name = ""
                    short_horizon_objective_name = ""
                    short_horizon_strategy_started_monotonic = now_monotonic
            if (
                self.gather_control_family == "region_funnel_v1"
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                decision = decide_region_funnel_pre_stage_command(
                    robot_pose,
                    ball_pose or {},
                    zone=self.zone,
                    snapshot=pre_stage_snapshot,
                    previous_strategy_name=short_horizon_strategy_name,
                    stall_s=max(0.0, now_monotonic - short_horizon_last_progress_monotonic),
                    strategy_elapsed_s=max(0.0, now_monotonic - short_horizon_strategy_started_monotonic),
                )
                if (
                    decision is not None
                    and bool(getattr(decision, "active", False))
                    and getattr(decision, "command", None) is not None
                ):
                    pre_stage_command = decision.command
                    pre_stage_strategy_name = str(getattr(decision, "strategy_name", "") or "")
                    pre_stage_objective_name = str(getattr(decision, "objective_name", "") or "")
                    pre_stage_progress_score = clean_number(getattr(decision, "progress_score", None))
                    pre_stage_projected_projection_gain = clean_number(
                        getattr(decision, "projected_projection_gain", None)
                    )
                    pre_stage_projected_lateral_gain = clean_number(
                        getattr(decision, "projected_lateral_gain", None)
                    )
                    pre_stage_projected_distance_gain = clean_number(
                        getattr(decision, "projected_distance_gain", None)
                    )
                    if (
                        pre_stage_progress_score is not None
                        and (
                            short_horizon_best_progress_score is None
                            or pre_stage_progress_score > short_horizon_best_progress_score + 1.0e-6
                        )
                    ):
                        short_horizon_best_progress_score = pre_stage_progress_score
                        short_horizon_last_progress_monotonic = now_monotonic
                    pre_stage_stall_s = max(0.0, now_monotonic - short_horizon_last_progress_monotonic)
                    if pre_stage_strategy_name != short_horizon_strategy_name:
                        short_horizon_strategy_started_monotonic = now_monotonic
                    short_horizon_strategy_name = pre_stage_strategy_name
                    short_horizon_objective_name = pre_stage_objective_name
            if (
                self.gather_control_family == CONSTRAINED_LOCAL_PLANNER_CONTROL_FAMILY
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                decision = decide_constrained_local_pre_stage_command(
                    robot_pose,
                    ball_pose or {},
                    zone=self.zone,
                    snapshot=pre_stage_snapshot,
                    previous_strategy_name=short_horizon_strategy_name,
                    stall_s=max(0.0, now_monotonic - short_horizon_last_progress_monotonic),
                    strategy_elapsed_s=max(0.0, now_monotonic - short_horizon_strategy_started_monotonic),
                    ball_motion_m=constrained_local_ball_motion_m,
                )
                constrained_local_debug_fields = {
                    "local_planner_candidate_count": int(getattr(decision, "candidate_count", 0) or 0),
                    "local_planner_accepted_count": int(getattr(decision, "accepted_count", 0) or 0),
                    "local_planner_rejected_count": int(getattr(decision, "rejected_count", 0) or 0),
                    "local_planner_rejection_reasons": list(getattr(decision, "rejection_reasons", ()) or ()),
                    "local_planner_projected_pre_stage": (
                        dict(getattr(decision, "projected_snapshot", {}) or {})
                        if isinstance(getattr(decision, "projected_snapshot", None), dict)
                        else {}
                    ),
                    "local_planner_release_reason": str(getattr(decision, "release_reason", "") or ""),
                    "local_planner_min_ball_clearance_m": clean_number(
                        getattr(decision, "min_ball_clearance_m", None)
                    ),
                    "local_planner_ball_motion_m": clean_number(getattr(decision, "ball_motion_m", None)),
                }
                if (
                    decision is not None
                    and bool(getattr(decision, "active", False))
                    and getattr(decision, "command", None) is not None
                ):
                    pre_stage_command = decision.command
                    pre_stage_strategy_name = str(getattr(decision, "strategy_name", "") or "")
                    pre_stage_objective_name = str(getattr(decision, "objective_name", "") or "")
                    pre_stage_progress_score = clean_number(getattr(decision, "progress_score", None))
                    pre_stage_projected_projection_gain = clean_number(
                        getattr(decision, "projected_projection_gain", None)
                    )
                    pre_stage_projected_lateral_gain = clean_number(
                        getattr(decision, "projected_lateral_gain", None)
                    )
                    pre_stage_projected_distance_gain = clean_number(
                        getattr(decision, "projected_distance_gain", None)
                    )
                    if (
                        pre_stage_progress_score is not None
                        and (
                            short_horizon_best_progress_score is None
                            or pre_stage_progress_score > short_horizon_best_progress_score + 1.0e-6
                        )
                    ):
                        short_horizon_best_progress_score = pre_stage_progress_score
                        short_horizon_last_progress_monotonic = now_monotonic
                    pre_stage_stall_s = max(0.0, now_monotonic - short_horizon_last_progress_monotonic)
                    if pre_stage_strategy_name != short_horizon_strategy_name:
                        short_horizon_strategy_started_monotonic = now_monotonic
                    short_horizon_strategy_name = pre_stage_strategy_name
                    short_horizon_objective_name = pre_stage_objective_name
                elif str(getattr(decision, "release_reason", "") or ""):
                    short_horizon_strategy_name = ""
                    short_horizon_objective_name = ""
                    short_horizon_strategy_started_monotonic = now_monotonic
            if (
                self.gather_control_family == DOCKING_REACQUIRE_CONTROL_FAMILY
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                decision = decide_docking_reacquire_pre_stage_command(
                    robot_pose,
                    ball_pose or {},
                    zone=self.zone,
                    snapshot=pre_stage_snapshot,
                    previous_strategy_name=short_horizon_strategy_name,
                    stall_s=max(0.0, now_monotonic - short_horizon_last_progress_monotonic),
                    strategy_elapsed_s=max(0.0, now_monotonic - short_horizon_strategy_started_monotonic),
                    ball_motion_m=docking_reacquire_ball_motion_m,
                )
                projected_snapshot = getattr(decision, "projected_snapshot", None)
                docking_reacquire_debug_fields = {
                    "docking_reacquire_active": bool(getattr(decision, "active", False)),
                    "docking_reacquire_release_reason": str(getattr(decision, "release_reason", "") or ""),
                    "docking_reacquire_release_blockers": list(getattr(decision, "release_blockers", ()) or ()),
                    "docking_reacquire_strategy_name": str(getattr(decision, "strategy_name", "") or ""),
                    "docking_reacquire_dock_pose": (
                        dict(getattr(decision, "dock_pose", {}) or {})
                        if isinstance(getattr(decision, "dock_pose", None), dict)
                        else {}
                    ),
                    "docking_reacquire_side_sign": clean_number(getattr(decision, "side_sign", None)),
                    "docking_reacquire_target_distance_m": clean_number(
                        getattr(decision, "target_distance_m", None)
                    ),
                    "docking_reacquire_target_heading_error_rad": clean_number(
                        getattr(decision, "target_heading_error_rad", None)
                    ),
                    "docking_reacquire_segment_ball_clearance_m": clean_number(
                        getattr(decision, "segment_ball_clearance_m", None)
                    ),
                    "docking_reacquire_min_ball_clearance_m": clean_number(
                        getattr(decision, "min_ball_clearance_m", None)
                    ),
                    "docking_reacquire_ball_motion_m": clean_number(
                        getattr(decision, "ball_motion_m", None)
                    ),
                    "docking_reacquire_projected_pre_stage": (
                        dict(projected_snapshot)
                        if isinstance(projected_snapshot, dict)
                        else {}
                    ),
                    "docking_reacquire_handoff_ready_measured": bool(
                        pre_stage_snapshot.get("pre_stage_pose_reached", False)
                    ),
                    "docking_reacquire_handoff_ready_projected": bool(
                        projected_snapshot.get("pre_stage_pose_reached", False)
                    )
                    if isinstance(projected_snapshot, dict)
                    else False,
                    "docking_reacquire_release_allowed": bool(
                        str(getattr(decision, "release_reason", "") or "")
                        and not list(getattr(decision, "release_blockers", ()) or ())
                    ),
                }
                if (
                    decision is not None
                    and bool(getattr(decision, "active", False))
                    and getattr(decision, "command", None) is not None
                ):
                    pre_stage_command = decision.command
                    pre_stage_strategy_name = str(getattr(decision, "strategy_name", "") or "")
                    pre_stage_objective_name = str(getattr(decision, "objective_name", "") or "")
                    pre_stage_progress_score = clean_number(getattr(decision, "progress_score", None))
                    pre_stage_projected_projection_gain = clean_number(
                        getattr(decision, "projected_projection_gain", None)
                    )
                    pre_stage_projected_lateral_gain = clean_number(
                        getattr(decision, "projected_lateral_gain", None)
                    )
                    pre_stage_projected_distance_gain = clean_number(
                        getattr(decision, "projected_distance_gain", None)
                    )
                    if (
                        pre_stage_progress_score is not None
                        and (
                            short_horizon_best_progress_score is None
                            or pre_stage_progress_score > short_horizon_best_progress_score + 1.0e-6
                        )
                    ):
                        short_horizon_best_progress_score = pre_stage_progress_score
                        short_horizon_last_progress_monotonic = now_monotonic
                    pre_stage_stall_s = max(0.0, now_monotonic - short_horizon_last_progress_monotonic)
                    if pre_stage_strategy_name != short_horizon_strategy_name:
                        short_horizon_strategy_started_monotonic = now_monotonic
                    short_horizon_strategy_name = pre_stage_strategy_name
                    short_horizon_objective_name = pre_stage_objective_name
                elif str(getattr(decision, "release_reason", "") or ""):
                    short_horizon_strategy_name = ""
                    short_horizon_objective_name = ""
                    short_horizon_strategy_started_monotonic = now_monotonic
            if (
                self.gather_control_family == HANDOFF_YAW_SERVO_CONTROL_FAMILY
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                decision = decide_handoff_yaw_servo_pre_stage_command(
                    robot_pose,
                    ball_pose or {},
                    zone=self.zone,
                    snapshot=pre_stage_snapshot,
                    ball_motion_m=handoff_yaw_servo_ball_motion_m,
                )
                projected_snapshot = getattr(decision, "projected_snapshot", None)
                handoff_yaw_servo_debug_fields = {
                    "handoff_yaw_servo_active": bool(getattr(decision, "active", False)),
                    "handoff_yaw_servo_release_reason": str(getattr(decision, "release_reason", "") or ""),
                    "handoff_yaw_servo_release_blockers": list(
                        getattr(decision, "release_blockers", ()) or ()
                    ),
                    "handoff_yaw_servo_strategy_name": str(getattr(decision, "strategy_name", "") or ""),
                    "handoff_yaw_servo_yaw_error_deg": clean_number(getattr(decision, "yaw_error_deg", None)),
                    "handoff_yaw_servo_yaw_error_rad": clean_number(getattr(decision, "yaw_error_rad", None)),
                    "handoff_yaw_servo_current_yaw_rad": clean_number(
                        getattr(decision, "current_yaw_rad", None)
                    ),
                    "handoff_yaw_servo_target_yaw_rad": clean_number(
                        getattr(decision, "target_yaw_rad", None)
                    ),
                    "handoff_yaw_servo_angular_z": clean_number(getattr(decision, "angular_z", None)),
                    "handoff_yaw_servo_ball_motion_m": clean_number(
                        getattr(decision, "ball_motion_m", None)
                    ),
                    "handoff_yaw_servo_projected_pre_stage": (
                        dict(projected_snapshot)
                        if isinstance(projected_snapshot, dict)
                        else {}
                    ),
                    "handoff_yaw_servo_handoff_ready_measured": bool(
                        pre_stage_snapshot.get("pre_stage_pose_reached", False)
                    ),
                    "handoff_yaw_servo_handoff_ready_projected": bool(
                        getattr(decision, "handoff_ready_projected", False)
                    ),
                }
                if (
                    decision is not None
                    and bool(getattr(decision, "active", False))
                    and getattr(decision, "command", None) is not None
                ):
                    pre_stage_command = decision.command
                    pre_stage_strategy_name = str(getattr(decision, "strategy_name", "") or "")
                    pre_stage_objective_name = str(getattr(decision, "objective_name", "") or "")
                    pre_stage_progress_score = clean_number(getattr(decision, "progress_score", None))
                    if (
                        pre_stage_progress_score is not None
                        and (
                            short_horizon_best_progress_score is None
                            or pre_stage_progress_score > short_horizon_best_progress_score + 1.0e-6
                        )
                    ):
                        short_horizon_best_progress_score = pre_stage_progress_score
                        short_horizon_last_progress_monotonic = now_monotonic
                    pre_stage_stall_s = max(0.0, now_monotonic - short_horizon_last_progress_monotonic)
                    if pre_stage_strategy_name != short_horizon_strategy_name:
                        short_horizon_strategy_started_monotonic = now_monotonic
                    short_horizon_strategy_name = pre_stage_strategy_name
                    short_horizon_objective_name = pre_stage_objective_name
                elif str(getattr(decision, "release_reason", "") or ""):
                    short_horizon_strategy_name = ""
                    short_horizon_objective_name = ""
                    short_horizon_strategy_started_monotonic = now_monotonic
            if (
                self.gather_control_family == PRE_STAGE_REACQUIRE_FSM_CONTROL_FAMILY
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                decision = decide_pre_stage_reacquire_fsm_command(
                    robot_pose,
                    ball_pose or {},
                    zone=self.zone,
                    snapshot=pre_stage_snapshot,
                    previous_phase=short_horizon_strategy_name,
                    ball_motion_m=pre_stage_reacquire_fsm_ball_motion_m,
                )
                projected_snapshot = getattr(decision, "projected_snapshot", None)
                measured_snapshot = getattr(decision, "measured_snapshot", None)
                measured_handoff_ready = getattr(decision, "measured_handoff_ready", None)
                projected_handoff_ready = getattr(decision, "projected_handoff_ready", None)
                pre_stage_reacquire_fsm_debug_fields = {
                    "pre_stage_reacquire_fsm_active": bool(getattr(decision, "active", False)),
                    "pre_stage_reacquire_fsm_phase": str(getattr(decision, "phase", "") or ""),
                    "pre_stage_reacquire_fsm_release_reason": str(
                        getattr(decision, "release_reason", "") or ""
                    ),
                    "pre_stage_reacquire_fsm_release_blockers": list(
                        getattr(decision, "release_blockers", ()) or ()
                    ),
                    "pre_stage_reacquire_fsm_measured_handoff_ready": (
                        bool(measured_handoff_ready) if measured_handoff_ready is not None else None
                    ),
                    "pre_stage_reacquire_fsm_projected_handoff_ready": (
                        bool(projected_handoff_ready) if projected_handoff_ready is not None else None
                    ),
                    "pre_stage_reacquire_fsm_measured_pre_stage": (
                        dict(measured_snapshot)
                        if isinstance(measured_snapshot, dict)
                        else {}
                    ),
                    "pre_stage_reacquire_fsm_projected_pre_stage": (
                        dict(projected_snapshot)
                        if isinstance(projected_snapshot, dict)
                        else {}
                    ),
                    "pre_stage_reacquire_fsm_projection_m": clean_number(
                        getattr(decision, "projection_m", None)
                    ),
                    "pre_stage_reacquire_fsm_lateral_error_m": clean_number(
                        getattr(decision, "lateral_error_m", None)
                    ),
                    "pre_stage_reacquire_fsm_distance_m": clean_number(
                        getattr(decision, "distance_m", None)
                    ),
                    "pre_stage_reacquire_fsm_yaw_error_deg": clean_number(
                        getattr(decision, "yaw_error_deg", None)
                    ),
                    "pre_stage_reacquire_fsm_projected_yaw_gain_deg": clean_number(
                        getattr(decision, "projected_yaw_gain_deg", None)
                    ),
                    "pre_stage_reacquire_fsm_ball_motion_m": clean_number(
                        getattr(decision, "ball_motion_m", None)
                    ),
                    "pre_stage_reacquire_fsm_min_ball_clearance_m": clean_number(
                        getattr(decision, "min_ball_clearance_m", None)
                    ),
                    "pre_stage_reacquire_fsm_target_pose": (
                        dict(getattr(decision, "target_pose", {}) or {})
                        if isinstance(getattr(decision, "target_pose", None), dict)
                        else {}
                    ),
                    "pre_stage_reacquire_fsm_target_distance_m": clean_number(
                        getattr(decision, "target_distance_m", None)
                    ),
                    "pre_stage_reacquire_fsm_target_heading_error_rad": clean_number(
                        getattr(decision, "target_heading_error_rad", None)
                    ),
                    "pre_stage_reacquire_fsm_candidate_count": int(
                        getattr(decision, "candidate_count", 0) or 0
                    ),
                    "pre_stage_reacquire_fsm_accepted_count": int(
                        getattr(decision, "accepted_count", 0) or 0
                    ),
                    "pre_stage_reacquire_fsm_rejected_count": int(
                        getattr(decision, "rejected_count", 0) or 0
                    ),
                    "pre_stage_reacquire_fsm_rejection_reasons": list(
                        getattr(decision, "rejection_reasons", ()) or ()
                    ),
                }
                if (
                    decision is not None
                    and bool(getattr(decision, "active", False))
                    and getattr(decision, "command", None) is not None
                ):
                    pre_stage_command = decision.command
                    pre_stage_strategy_name = str(getattr(decision, "strategy_name", "") or "")
                    pre_stage_objective_name = str(getattr(decision, "objective_name", "") or "")
                    pre_stage_progress_score = clean_number(getattr(decision, "progress_score", None))
                    pre_stage_projected_projection_gain = clean_number(
                        getattr(decision, "projected_projection_gain", None)
                    )
                    pre_stage_projected_lateral_gain = clean_number(
                        getattr(decision, "projected_lateral_gain", None)
                    )
                    pre_stage_projected_distance_gain = clean_number(
                        getattr(decision, "projected_distance_gain", None)
                    )
                    if (
                        pre_stage_progress_score is not None
                        and (
                            short_horizon_best_progress_score is None
                            or pre_stage_progress_score > short_horizon_best_progress_score + 1.0e-6
                        )
                    ):
                        short_horizon_best_progress_score = pre_stage_progress_score
                        short_horizon_last_progress_monotonic = now_monotonic
                    pre_stage_stall_s = max(0.0, now_monotonic - short_horizon_last_progress_monotonic)
                    if pre_stage_strategy_name != short_horizon_strategy_name:
                        short_horizon_strategy_started_monotonic = now_monotonic
                    short_horizon_strategy_name = pre_stage_strategy_name
                    short_horizon_objective_name = pre_stage_objective_name
                elif str(getattr(decision, "release_reason", "") or ""):
                    if str(getattr(decision, "release_reason", "") or "") == "ball_motion_guard":
                        pre_stage_reacquire_fsm_abort_reason = "pre_stage_ball_motion_guard"
                        pre_stage_command = PlaceControlCommand(
                            mode="pre_stage_reacquire_fsm_abort",
                            linear_x=0.0,
                            angular_z=0.0,
                            target_speed_scale=0.0,
                            rationale="Pre-stage reacquire FSM stopped because ball motion was detected before handoff.",
                        )
                    short_horizon_strategy_name = ""
                    short_horizon_objective_name = ""
                    short_horizon_strategy_started_monotonic = now_monotonic
            if (
                self.gather_control_family == PRE_STAGE_PATH_TRACKER_CONTROL_FAMILY
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                decision = decide_pre_stage_path_tracker_command(
                    robot_pose,
                    ball_pose or {},
                    zone=self.zone,
                    snapshot=pre_stage_snapshot,
                    previous_waypoint_index=pre_stage_path_tracker_waypoint_index,
                    stall_s=max(0.0, now_monotonic - short_horizon_last_progress_monotonic),
                    ball_motion_m=pre_stage_path_tracker_ball_motion_m,
                )
                projected_snapshot = getattr(decision, "projected_snapshot", None)
                measured_snapshot = getattr(decision, "measured_snapshot", None)
                measured_handoff_ready = getattr(decision, "measured_handoff_ready", None)
                projected_handoff_ready = getattr(decision, "projected_handoff_ready", None)
                pre_stage_path_tracker_waypoint_index = int(
                    getattr(decision, "waypoint_index", pre_stage_path_tracker_waypoint_index) or 0
                )
                pre_stage_path_tracker_debug_fields = {
                    "pre_stage_path_tracker_active": bool(getattr(decision, "active", False)),
                    "pre_stage_path_tracker_waypoint_index": int(
                        getattr(decision, "waypoint_index", 0) or 0
                    ),
                    "pre_stage_path_tracker_waypoint_kind": str(
                        getattr(decision, "waypoint_kind", "") or ""
                    ),
                    "pre_stage_path_tracker_waypoint_count": int(
                        getattr(decision, "waypoint_count", 0) or 0
                    ),
                    "pre_stage_path_tracker_release_reason": str(
                        getattr(decision, "release_reason", "") or ""
                    ),
                    "pre_stage_path_tracker_release_blockers": list(
                        getattr(decision, "release_blockers", ()) or ()
                    ),
                    "pre_stage_path_tracker_measured_handoff_ready": (
                        bool(measured_handoff_ready) if measured_handoff_ready is not None else None
                    ),
                    "pre_stage_path_tracker_projected_handoff_ready": (
                        bool(projected_handoff_ready) if projected_handoff_ready is not None else None
                    ),
                    "pre_stage_path_tracker_measured_pre_stage": (
                        dict(measured_snapshot)
                        if isinstance(measured_snapshot, dict)
                        else {}
                    ),
                    "pre_stage_path_tracker_projected_pre_stage": (
                        dict(projected_snapshot)
                        if isinstance(projected_snapshot, dict)
                        else {}
                    ),
                    "pre_stage_path_tracker_waypoint_pose": (
                        dict(getattr(decision, "waypoint_pose", {}) or {})
                        if isinstance(getattr(decision, "waypoint_pose", None), dict)
                        else {}
                    ),
                    "pre_stage_path_tracker_waypoint_distance_m": clean_number(
                        getattr(decision, "waypoint_distance_m", None)
                    ),
                    "pre_stage_path_tracker_waypoint_heading_error_rad": clean_number(
                        getattr(decision, "waypoint_heading_error_rad", None)
                    ),
                    "pre_stage_path_tracker_waypoint_reached": bool(
                        getattr(decision, "waypoint_reached", False)
                    ),
                    "pre_stage_path_tracker_projection_m": clean_number(
                        getattr(decision, "projection_m", None)
                    ),
                    "pre_stage_path_tracker_lateral_error_m": clean_number(
                        getattr(decision, "lateral_error_m", None)
                    ),
                    "pre_stage_path_tracker_distance_m": clean_number(
                        getattr(decision, "distance_m", None)
                    ),
                    "pre_stage_path_tracker_yaw_error_deg": clean_number(
                        getattr(decision, "yaw_error_deg", None)
                    ),
                    "pre_stage_path_tracker_projected_yaw_gain_deg": clean_number(
                        getattr(decision, "projected_yaw_gain_deg", None)
                    ),
                    "pre_stage_path_tracker_ball_motion_m": clean_number(
                        getattr(decision, "ball_motion_m", None)
                    ),
                    "pre_stage_path_tracker_min_ball_clearance_m": clean_number(
                        getattr(decision, "min_ball_clearance_m", None)
                    ),
                    "pre_stage_path_tracker_segment_ball_clearance_m": clean_number(
                        getattr(decision, "segment_ball_clearance_m", None)
                    ),
                    "pre_stage_path_tracker_candidate_count": int(
                        getattr(decision, "candidate_count", 0) or 0
                    ),
                    "pre_stage_path_tracker_accepted_count": int(
                        getattr(decision, "accepted_count", 0) or 0
                    ),
                    "pre_stage_path_tracker_rejected_count": int(
                        getattr(decision, "rejected_count", 0) or 0
                    ),
                    "pre_stage_path_tracker_rejection_reasons": list(
                        getattr(decision, "rejection_reasons", ()) or ()
                    ),
                    "pre_stage_path_tracker_progress_timeout": "waypoint_progress_stall"
                    in list(getattr(decision, "rejection_reasons", ()) or ()),
                }
                if (
                    decision is not None
                    and bool(getattr(decision, "active", False))
                    and getattr(decision, "command", None) is not None
                ):
                    pre_stage_command = decision.command
                    pre_stage_strategy_name = str(getattr(decision, "strategy_name", "") or "")
                    pre_stage_objective_name = str(getattr(decision, "objective_name", "") or "")
                    pre_stage_progress_score = clean_number(getattr(decision, "progress_score", None))
                    pre_stage_projected_projection_gain = clean_number(
                        getattr(decision, "projected_projection_gain", None)
                    )
                    pre_stage_projected_lateral_gain = clean_number(
                        getattr(decision, "projected_lateral_gain", None)
                    )
                    pre_stage_projected_distance_gain = clean_number(
                        getattr(decision, "projected_distance_gain", None)
                    )
                    if (
                        pre_stage_progress_score is not None
                        and (
                            short_horizon_best_progress_score is None
                            or pre_stage_progress_score > short_horizon_best_progress_score + 1.0e-6
                        )
                    ):
                        short_horizon_best_progress_score = pre_stage_progress_score
                        short_horizon_last_progress_monotonic = now_monotonic
                    pre_stage_stall_s = max(0.0, now_monotonic - short_horizon_last_progress_monotonic)
                    if pre_stage_strategy_name != short_horizon_strategy_name:
                        short_horizon_strategy_started_monotonic = now_monotonic
                    short_horizon_strategy_name = pre_stage_strategy_name
                    short_horizon_objective_name = pre_stage_objective_name
                elif str(getattr(decision, "release_reason", "") or ""):
                    if str(getattr(decision, "release_reason", "") or "") == "ball_motion_guard":
                        pre_stage_path_tracker_abort_reason = "pre_stage_path_tracker_ball_motion_guard"
                        pre_stage_command = PlaceControlCommand(
                            mode="pre_stage_path_tracker_abort",
                            linear_x=0.0,
                            angular_z=0.0,
                            target_speed_scale=0.0,
                            rationale="Pre-stage path tracker stopped because ball motion was detected before handoff.",
                        )
                    short_horizon_strategy_name = ""
                    short_horizon_objective_name = ""
                    short_horizon_strategy_started_monotonic = now_monotonic
            if (
                self.gather_control_family == PRE_STAGE_TRAJECTORY_OWNER_CONTROL_FAMILY
                and robot_pose
                and ball_pose
                and isinstance(pre_stage_snapshot, dict)
            ):
                decision = decide_pre_stage_trajectory_owner_command(
                    robot_pose,
                    ball_pose or {},
                    zone=self.zone,
                    snapshot=pre_stage_snapshot,
                    previous_milestone_index=pre_stage_trajectory_owner_milestone_index,
                    stall_s=max(0.0, now_monotonic - short_horizon_last_progress_monotonic),
                    ball_motion_m=pre_stage_trajectory_owner_ball_motion_m,
                    side_sign=pre_stage_trajectory_owner_side_sign,
                    replan_count=pre_stage_trajectory_owner_replan_count,
                )
                projected_snapshot = getattr(decision, "projected_snapshot", None)
                measured_snapshot = getattr(decision, "measured_snapshot", None)
                measured_handoff_ready = getattr(decision, "measured_handoff_ready", None)
                projected_handoff_ready = getattr(decision, "projected_handoff_ready", None)
                previous_replan_count = pre_stage_trajectory_owner_replan_count
                pre_stage_trajectory_owner_milestone_index = int(
                    getattr(decision, "milestone_index", pre_stage_trajectory_owner_milestone_index) or 0
                )
                next_replan_count = int(
                    getattr(decision, "next_replan_count", pre_stage_trajectory_owner_replan_count) or 0
                )
                next_side_sign = clean_number(getattr(decision, "next_side_sign", None))
                if next_side_sign is not None:
                    pre_stage_trajectory_owner_side_sign = 1.0 if next_side_sign >= 0.0 else -1.0
                if next_replan_count > pre_stage_trajectory_owner_replan_count:
                    pre_stage_trajectory_owner_replan_count = next_replan_count
                    pre_stage_trajectory_owner_milestone_index = 0
                    short_horizon_best_progress_score = None
                    short_horizon_last_progress_monotonic = now_monotonic
                    short_horizon_strategy_started_monotonic = now_monotonic
                pre_stage_trajectory_owner_debug_fields = {
                    "pre_stage_trajectory_owner_active": bool(getattr(decision, "active", False)),
                    "pre_stage_trajectory_owner_milestone_index": int(
                        getattr(decision, "milestone_index", 0) or 0
                    ),
                    "pre_stage_trajectory_owner_milestone_kind": str(
                        getattr(decision, "milestone_kind", "") or ""
                    ),
                    "pre_stage_trajectory_owner_milestone_count": int(
                        getattr(decision, "milestone_count", 0) or 0
                    ),
                    "pre_stage_trajectory_owner_target_pose": (
                        dict(getattr(decision, "target_pose", {}) or {})
                        if isinstance(getattr(decision, "target_pose", None), dict)
                        else {}
                    ),
                    "pre_stage_trajectory_owner_target_distance_m": clean_number(
                        getattr(decision, "target_distance_m", None)
                    ),
                    "pre_stage_trajectory_owner_target_heading_error_rad": clean_number(
                        getattr(decision, "target_heading_error_rad", None)
                    ),
                    "pre_stage_trajectory_owner_milestone_reached": bool(
                        getattr(decision, "milestone_reached", False)
                    ),
                    "pre_stage_trajectory_owner_progress_rate_mps": clean_number(
                        getattr(decision, "progress_rate_mps", None)
                    ),
                    "pre_stage_trajectory_owner_side_sign": clean_number(
                        getattr(decision, "side_sign", None)
                    ),
                    "pre_stage_trajectory_owner_next_side_sign": clean_number(
                        getattr(decision, "next_side_sign", None)
                    ),
                    "pre_stage_trajectory_owner_replan_count": int(
                        getattr(decision, "replan_count", previous_replan_count) or 0
                    ),
                    "pre_stage_trajectory_owner_next_replan_count": next_replan_count,
                    "pre_stage_trajectory_owner_replan_reason": str(
                        getattr(decision, "replan_reason", "") or ""
                    ),
                    "pre_stage_trajectory_owner_release_reason": str(
                        getattr(decision, "release_reason", "") or ""
                    ),
                    "pre_stage_trajectory_owner_release_blockers": list(
                        getattr(decision, "release_blockers", ()) or ()
                    ),
                    "pre_stage_trajectory_owner_measured_handoff_ready": (
                        bool(measured_handoff_ready) if measured_handoff_ready is not None else None
                    ),
                    "pre_stage_trajectory_owner_projected_handoff_ready": (
                        bool(projected_handoff_ready) if projected_handoff_ready is not None else None
                    ),
                    "pre_stage_trajectory_owner_measured_pre_stage": (
                        dict(measured_snapshot)
                        if isinstance(measured_snapshot, dict)
                        else {}
                    ),
                    "pre_stage_trajectory_owner_projected_pre_stage": (
                        dict(projected_snapshot)
                        if isinstance(projected_snapshot, dict)
                        else {}
                    ),
                    "pre_stage_trajectory_owner_projection_m": clean_number(
                        getattr(decision, "projection_m", None)
                    ),
                    "pre_stage_trajectory_owner_lateral_error_m": clean_number(
                        getattr(decision, "lateral_error_m", None)
                    ),
                    "pre_stage_trajectory_owner_distance_m": clean_number(
                        getattr(decision, "distance_m", None)
                    ),
                    "pre_stage_trajectory_owner_yaw_error_deg": clean_number(
                        getattr(decision, "yaw_error_deg", None)
                    ),
                    "pre_stage_trajectory_owner_projected_projection_gain": clean_number(
                        getattr(decision, "projected_projection_gain", None)
                    ),
                    "pre_stage_trajectory_owner_projected_lateral_gain": clean_number(
                        getattr(decision, "projected_lateral_gain", None)
                    ),
                    "pre_stage_trajectory_owner_projected_distance_gain": clean_number(
                        getattr(decision, "projected_distance_gain", None)
                    ),
                    "pre_stage_trajectory_owner_projected_yaw_gain_deg": clean_number(
                        getattr(decision, "projected_yaw_gain_deg", None)
                    ),
                    "pre_stage_trajectory_owner_ball_motion_m": clean_number(
                        getattr(decision, "ball_motion_m", None)
                    ),
                    "pre_stage_trajectory_owner_min_ball_clearance_m": clean_number(
                        getattr(decision, "min_ball_clearance_m", None)
                    ),
                    "pre_stage_trajectory_owner_segment_ball_clearance_m": clean_number(
                        getattr(decision, "segment_ball_clearance_m", None)
                    ),
                    "pre_stage_trajectory_owner_measured_ball_clearance_m": clean_number(
                        getattr(decision, "measured_ball_clearance_m", None)
                    ),
                    "pre_stage_trajectory_owner_candidate_count": int(
                        getattr(decision, "candidate_count", 0) or 0
                    ),
                    "pre_stage_trajectory_owner_accepted_count": int(
                        getattr(decision, "accepted_count", 0) or 0
                    ),
                    "pre_stage_trajectory_owner_rejected_count": int(
                        getattr(decision, "rejected_count", 0) or 0
                    ),
                    "pre_stage_trajectory_owner_rejection_reasons": list(
                        getattr(decision, "rejection_reasons", ()) or ()
                    ),
                }
                if (
                    decision is not None
                    and bool(getattr(decision, "active", False))
                    and getattr(decision, "command", None) is not None
                ):
                    pre_stage_command = decision.command
                    pre_stage_strategy_name = str(getattr(decision, "strategy_name", "") or "")
                    pre_stage_objective_name = str(getattr(decision, "objective_name", "") or "")
                    pre_stage_progress_score = clean_number(getattr(decision, "progress_score", None))
                    pre_stage_projected_projection_gain = clean_number(
                        getattr(decision, "projected_projection_gain", None)
                    )
                    pre_stage_projected_lateral_gain = clean_number(
                        getattr(decision, "projected_lateral_gain", None)
                    )
                    pre_stage_projected_distance_gain = clean_number(
                        getattr(decision, "projected_distance_gain", None)
                    )
                    if (
                        pre_stage_progress_score is not None
                        and (
                            short_horizon_best_progress_score is None
                            or pre_stage_progress_score > short_horizon_best_progress_score + 1.0e-6
                        )
                    ):
                        short_horizon_best_progress_score = pre_stage_progress_score
                        short_horizon_last_progress_monotonic = now_monotonic
                    pre_stage_stall_s = max(0.0, now_monotonic - short_horizon_last_progress_monotonic)
                    if pre_stage_strategy_name != short_horizon_strategy_name:
                        short_horizon_strategy_started_monotonic = now_monotonic
                    short_horizon_strategy_name = pre_stage_strategy_name
                    short_horizon_objective_name = pre_stage_objective_name
                elif str(getattr(decision, "release_reason", "") or ""):
                    release_reason = str(getattr(decision, "release_reason", "") or "")
                    if release_reason == "ball_motion_guard":
                        pre_stage_trajectory_owner_abort_reason = "pre_stage_trajectory_owner_ball_motion_guard"
                    elif release_reason == "trajectory_clearance_guard":
                        pre_stage_trajectory_owner_abort_reason = "pre_stage_trajectory_owner_clearance_guard"
                    elif release_reason == "trajectory_progress_stalled":
                        pre_stage_trajectory_owner_abort_reason = "pre_stage_trajectory_owner_progress_stalled"
                    if pre_stage_trajectory_owner_abort_reason:
                        pre_stage_command = PlaceControlCommand(
                            mode="pre_stage_trajectory_owner_abort",
                            linear_x=0.0,
                            angular_z=0.0,
                            target_speed_scale=0.0,
                            rationale="Pre-stage trajectory owner stopped before measured handoff.",
                        )
                    short_horizon_strategy_name = ""
                    short_horizon_objective_name = ""
                    short_horizon_strategy_started_monotonic = now_monotonic
            if pre_stage_command is not None:
                latest_pre_capture_command_mode = str(pre_stage_command.mode)
            pre_stage_manager_decision = decide_gather_manager_directive(
                GatherManagerState(
                    phase="pre_stage",
                    phase_elapsed_s=now_monotonic - pre_stage_started_monotonic,
                    pre_stage_snapshot=pre_stage_snapshot or {},
                    approach_snapshot=pre_stage_snapshot or {},
                    capture_snapshot=capture.to_dict() if capture else {},
                    phase_ready_observed=pre_stage_ready_signal,
                    attempt_kind=attempt_kind,
                    latest_command_mode=latest_pre_capture_command_mode,
                )
            )
            self._update_gather_runtime_state(
                mission_phase="pre_stage",
                gather_phase="pre_stage",
                current_target_id=target.id,
                capture_state=capture.to_dict() if capture else {},
                zone_score=zone_score.to_dict() if zone_score else {},
                latest_feedback=f"Navigating behind {target.label} before staging.",
            )
            self._update_visit_runtime_state(
                proof_state="visiting",
                mission_phase="pre_stage",
                current_target_id=target.id,
                latest_feedback=f"Navigating behind {target.label} before staging.",
            )
            append_jsonl(
                state_history_path,
                {
                    "generated_utc": utc_now(),
                    "phase": "pre_stage",
                    "attempt": int(attempt_index),
                    "attempt_kind": str(attempt_kind),
                    "target_id": target.id,
                    "robot_pose": robot_pose,
                    "ball_pose": ball_pose,
                    "capture": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "pre_stage": pre_stage_snapshot or {},
                    "manager_directive": pre_stage_manager_decision.directive,
                    "selected_command": pre_stage_command.to_dict() if pre_stage_command else {},
                    **self._control_debug_fields(
                        strategy_name=pre_stage_strategy_name,
                        objective_name=pre_stage_objective_name,
                        progress_score=pre_stage_progress_score,
                        stall_s=pre_stage_stall_s,
                        projected_projection_gain=pre_stage_projected_projection_gain,
                        projected_lateral_gain=pre_stage_projected_lateral_gain,
                        projected_distance_gain=pre_stage_projected_distance_gain,
                    ),
                    **constrained_local_debug_fields,
                    **docking_reacquire_debug_fields,
                    **handoff_yaw_servo_debug_fields,
                    **pre_stage_reacquire_fsm_debug_fields,
                    **pre_stage_path_tracker_debug_fields,
                    **pre_stage_trajectory_owner_debug_fields,
                    **object_centric_debug_fields,
                },
            )
            if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                object_centric_previous_command = pre_stage_command
                object_centric_previous_ball_pose = dict(ball_pose or {}) if ball_pose else object_centric_previous_ball_pose
            constrained_local_previous_ball_pose = dict(ball_pose or {}) if ball_pose else constrained_local_previous_ball_pose
            docking_reacquire_previous_ball_pose = (
                dict(ball_pose or {}) if ball_pose else docking_reacquire_previous_ball_pose
            )
            handoff_yaw_servo_previous_ball_pose = (
                dict(ball_pose or {}) if ball_pose else handoff_yaw_servo_previous_ball_pose
            )
            pre_stage_reacquire_fsm_previous_ball_pose = (
                dict(ball_pose or {}) if ball_pose else pre_stage_reacquire_fsm_previous_ball_pose
            )
            pre_stage_path_tracker_previous_ball_pose = (
                dict(ball_pose or {}) if ball_pose else pre_stage_path_tracker_previous_ball_pose
            )
            pre_stage_trajectory_owner_previous_ball_pose = (
                dict(ball_pose or {}) if ball_pose else pre_stage_trajectory_owner_previous_ball_pose
            )
            if pre_stage_reacquire_fsm_abort_reason:
                pre_stage_time_s = now_monotonic - pre_stage_started_monotonic
                self._set_manual_drive(
                    enabled=False,
                    mode=pre_stage_reacquire_fsm_abort_reason,
                    rationale="Pre-stage reacquire FSM stopped before handoff because its safety guard tripped.",
                )
                failure_payload = {
                    "failure_reason": pre_stage_reacquire_fsm_abort_reason,
                    "failure_stage": "pre_stage",
                    "pre_stage_pose_world": pre_stage_pose_world,
                    "pre_stage_pose_reached": bool(pre_stage_pose_reached_once),
                    "pre_stage_time_s": round(pre_stage_time_s, 6),
                    "pre_stage_handoff_pass": False,
                    "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                    "approach_failure_reason": "ball_motion_guard",
                    "entered_goal_side_before_capture": False,
                }
                write_json(mission_root / f"{target.id}_{pre_stage_reacquire_fsm_abort_reason}.json", failure_payload)
                return False, failure_payload
            if pre_stage_path_tracker_abort_reason:
                pre_stage_time_s = now_monotonic - pre_stage_started_monotonic
                self._set_manual_drive(
                    enabled=False,
                    mode=pre_stage_path_tracker_abort_reason,
                    rationale="Pre-stage path tracker stopped before handoff because its safety guard tripped.",
                )
                failure_payload = {
                    "failure_reason": pre_stage_path_tracker_abort_reason,
                    "failure_stage": "pre_stage",
                    "pre_stage_pose_world": pre_stage_pose_world,
                    "pre_stage_pose_reached": bool(pre_stage_pose_reached_once),
                    "pre_stage_time_s": round(pre_stage_time_s, 6),
                    "pre_stage_handoff_pass": False,
                    "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                    "approach_failure_reason": "ball_motion_guard",
                    "entered_goal_side_before_capture": False,
                }
                write_json(mission_root / f"{target.id}_{pre_stage_path_tracker_abort_reason}.json", failure_payload)
                return False, failure_payload
            if pre_stage_trajectory_owner_abort_reason:
                pre_stage_time_s = now_monotonic - pre_stage_started_monotonic
                self._set_manual_drive(
                    enabled=False,
                    mode=pre_stage_trajectory_owner_abort_reason,
                    rationale="Pre-stage trajectory owner stopped before handoff because its guard tripped.",
                )
                release_reason = str(
                    pre_stage_trajectory_owner_debug_fields.get(
                        "pre_stage_trajectory_owner_release_reason",
                        "",
                    )
                    or ""
                )
                failure_payload = {
                    "failure_reason": pre_stage_trajectory_owner_abort_reason,
                    "failure_stage": "pre_stage",
                    "pre_stage_pose_world": pre_stage_pose_world,
                    "pre_stage_pose_reached": bool(pre_stage_pose_reached_once),
                    "pre_stage_time_s": round(pre_stage_time_s, 6),
                    "pre_stage_handoff_pass": False,
                    "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                    "approach_failure_reason": release_reason,
                    "entered_goal_side_before_capture": False,
                }
                write_json(mission_root / f"{target.id}_{pre_stage_trajectory_owner_abort_reason}.json", failure_payload)
                return False, failure_payload
            if (
                pre_stage_manager_decision.directive == "stabilize_stage"
                and
                pre_stage_ready_started_monotonic is not None
                and (now_monotonic - pre_stage_ready_started_monotonic) >= DEFAULT_PRE_STAGE_READY_DWELL_S
            ):
                pre_stage_time_s = now_monotonic - pre_stage_started_monotonic
                self._set_manual_drive(
                    enabled=False,
                    mode="pre_stage_ready",
                    rationale="Robot reached the coarse behind-ball arrival pose; handing off to fine staging.",
                )
                return True, {
                    "pre_stage_pose_world": pre_stage_pose_world,
                    "pre_stage_pose_reached": True,
                    "pre_stage_time_s": round(pre_stage_time_s, 6),
                    "pre_stage_timeout_budget_s": round(pre_stage_timeout_s, 6),
                    "pre_stage_handoff_pass": True,
                    "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                    "object_centric_policy": last_object_centric_policy,
                }
            if pre_stage_command is not None:
                self._set_manual_drive(
                    enabled=True,
                    linear_x=pre_stage_command.linear_x,
                    angular_z=pre_stage_command.angular_z,
                    mode=pre_stage_command.mode,
                    rationale=pre_stage_command.rationale,
                )
                self._update_gather_runtime_state(latest_control_command=pre_stage_command.to_dict())
            time.sleep(self.args.poll_s)

        pre_stage_time_s = time.monotonic() - pre_stage_started_monotonic
        self._set_manual_drive(
            enabled=False,
            mode="pre_stage_timeout",
            rationale="Coarse behind-ball arrival timed out before fine staging could begin.",
        )
        timeout_payload = {
            "failure_reason": "pre_stage_timeout",
            "failure_stage": "pre_stage",
            "pre_stage_pose_world": pre_stage_pose_world,
            "pre_stage_pose_reached": bool(pre_stage_pose_reached_once),
            "pre_stage_time_s": round(pre_stage_time_s, 6),
            "pre_stage_timeout_budget_s": round(pre_stage_timeout_s, 6),
            "pre_stage_handoff_pass": False,
            "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
            "approach_failure_reason": last_failure_reason,
            "entered_goal_side_before_capture": last_failure_reason == "entered_goal_side_before_capture",
            "object_centric_policy": last_object_centric_policy,
        }
        write_json(mission_root / f"{target.id}_pre_stage_timeout.json", timeout_payload)
        return False, timeout_payload

    def _capture_target(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
        state_history_path: Path,
        mission_root: Path,
        prefer_zone_recovery: bool = False,
        enable_goal_side_stage: bool = False,
        attempt_index: int = 0,
        attempt_kind: str = "",
    ) -> tuple[bool, dict[str, Any]]:
        capture_timeout_s = max(self.args.capture_timeout_s, 0.1)
        if (
            self.mission_objective == MISSION_OBJECTIVE_FETCH_TO_POSE
            and self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
        ):
            capture_timeout_s = max(capture_timeout_s, DEFAULT_OBJECT_CENTRIC_FETCH_CAPTURE_TIMEOUT_S)
        deadline = time.monotonic() + capture_timeout_s
        captured_started_monotonic: float | None = None
        zone_centered_started_monotonic: float | None = None
        previous_ball_pose: dict[str, Any] | None = None
        last_capture = None
        last_zone_score = None
        stage_started_monotonic = time.monotonic() if enable_goal_side_stage else None
        stage_timeout_s = (
            DEFAULT_OBJECT_CENTRIC_STAGE_TIMEOUT_S
            if (
                enable_goal_side_stage
                and self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
            )
            else DEFAULT_STAGE_TIMEOUT_S
        )
        stage_ready_started_monotonic: float | None = None
        stage_ready_latched = False
        stage_completed = not enable_goal_side_stage
        capture_entry_started_monotonic: float | None = None
        capture_entry_ready_started_monotonic: float | None = None
        capture_entry_ready_latched = False
        capture_entry_completed = not enable_goal_side_stage
        staging_pose_reached_once = False
        capture_entry_reached_once = False
        entered_goal_side_before_capture = False
        first_contact_alignment_value: float | None = None
        stage_time_s = 0.0
        capture_entry_time_s = 0.0
        push_direction_yaw_deg = 0.0
        approach_failure_reason = ""
        last_approach_snapshot: dict[str, Any] = {}
        latest_pre_capture_command_mode = ""
        handoff_robot_pose: dict[str, Any] | None = None
        handoff_ball_pose: dict[str, Any] | None = None
        last_capture_entry_snapshot: dict[str, Any] = {}
        last_capture_entry_diagnostics: dict[str, Any] = {}
        capture_handoff_robot_pose: dict[str, Any] | None = None
        capture_handoff_ball_pose: dict[str, Any] | None = None
        capture_started_monotonic: float | None = None
        last_capture_diagnostics: dict[str, Any] = {}
        object_centric_previous_command: PlaceControlCommand | None = None
        object_centric_previous_ball_pose: dict[str, Any] | None = None
        last_object_centric_policy: dict[str, Any] = {}

        def _capture_entry_timeout_cause(*, manager_directive: str = "") -> str:
            directive = str(manager_directive or "")
            if (
                directive == "recover_goal_side"
                or approach_failure_reason == "capture_entry_goal_side_loss"
                or entered_goal_side_before_capture
            ):
                return "goal_side_authority_lost"
            if capture_entry_reached_once or capture_entry_ready_latched:
                return "ready_dwell_not_completed"
            return "ready_band_never_reached"

        def _capture_entry_diagnostics_payload(
            *,
            now_monotonic: float,
            snapshot: dict[str, Any] | None,
            ready_signal: bool,
            manager_directive: str,
            selected_command: Any = None,
            robot_pose: dict[str, Any] | None = None,
            ball_pose: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            capture_entry_elapsed_s = 0.0
            if capture_entry_started_monotonic is not None:
                capture_entry_elapsed_s = max(0.0, now_monotonic - float(capture_entry_started_monotonic))
            ready_dwell_s = 0.0
            if capture_entry_ready_started_monotonic is not None:
                ready_dwell_s = max(0.0, now_monotonic - float(capture_entry_ready_started_monotonic))
            snapshot_payload = dict(snapshot or {})
            selected_command_payload = selected_command.to_dict() if selected_command is not None else {}
            robot_delta_m = (
                pose_delta_m(handoff_robot_pose, robot_pose)
                if handoff_robot_pose is not None and robot_pose is not None
                else None
            )
            ball_delta_m = (
                pose_delta_m(handoff_ball_pose, ball_pose)
                if handoff_ball_pose is not None and ball_pose is not None
                else None
            )
            return {
                "elapsed_s": round(float(capture_entry_elapsed_s), 6),
                "timeout_s": round(float(DEFAULT_CAPTURE_ENTRY_TIMEOUT_S), 6),
                "ready_signal": bool(ready_signal),
                "ready_latched": bool(capture_entry_ready_latched),
                "ready_reached_once": bool(capture_entry_reached_once),
                "ready_dwell_s": round(float(ready_dwell_s), 6),
                "ready_dwell_required_s": round(float(DEFAULT_CAPTURE_ENTRY_READY_DWELL_S), 6),
                "ready_dwell_completed": bool(
                    capture_entry_ready_started_monotonic is not None
                    and ready_dwell_s >= DEFAULT_CAPTURE_ENTRY_READY_DWELL_S
                ),
                "timeout_cause": _capture_entry_timeout_cause(manager_directive=manager_directive),
                "manager_directive": str(manager_directive or ""),
                "selected_command": selected_command_payload,
                "selected_command_mode": str(selected_command_payload.get("mode", "") or ""),
                "robot_delta_from_handoff_m": clean_rounded_number(robot_delta_m),
                "ball_delta_from_handoff_m": clean_rounded_number(ball_delta_m),
                "handoff_robot_pose": dict(handoff_robot_pose or {}),
                "handoff_ball_pose": dict(handoff_ball_pose or {}),
                "capture_entry_snapshot": snapshot_payload,
                "ball_x_m": clean_rounded_number(snapshot_payload.get("ball_x_m")),
                "ball_y_m": clean_rounded_number(snapshot_payload.get("ball_y_m")),
                "bearing_rad": clean_rounded_number(snapshot_payload.get("bearing_rad")),
                "robot_longitudinal_projection_m": clean_rounded_number(
                    snapshot_payload.get("robot_longitudinal_projection_m")
                ),
                "robot_lateral_error_m": clean_rounded_number(snapshot_payload.get("robot_lateral_error_m")),
                "robot_on_goal_side": bool(snapshot_payload.get("robot_on_goal_side", False)),
                "entered_goal_side_before_capture": bool(entered_goal_side_before_capture),
            }

        def _command_payload(command: Any = None) -> dict[str, Any]:
            if command is None:
                return {}
            if isinstance(command, dict):
                return dict(command)
            to_dict = getattr(command, "to_dict", None)
            if callable(to_dict):
                payload = to_dict()
                return dict(payload) if isinstance(payload, dict) else {}
            return {}

        def _capture_diagnostics_payload(
            *,
            now_monotonic: float,
            capture: Any = None,
            zone_score: Any = None,
            approach_snapshot: dict[str, Any] | None = None,
            selected_command: Any = None,
            raw_command: Any = None,
            command_source: str = "",
            command_limit_reason: str = "",
            robot_pose: dict[str, Any] | None = None,
            ball_pose: dict[str, Any] | None = None,
            zone_entry_handoff_ready: bool = False,
            secure_capture_ready: bool = False,
            soft_capture_handoff_ready: bool = False,
            terminal_cause: str = "",
        ) -> dict[str, Any]:
            capture_elapsed_s = 0.0
            if capture_started_monotonic is not None:
                capture_elapsed_s = max(0.0, now_monotonic - float(capture_started_monotonic))
            selected_command_payload = _command_payload(selected_command)
            raw_command_payload = _command_payload(raw_command)
            robot_delta_m = (
                pose_delta_m(capture_handoff_robot_pose, robot_pose)
                if capture_handoff_robot_pose is not None and robot_pose is not None
                else None
            )
            ball_delta_m = (
                pose_delta_m(capture_handoff_ball_pose, ball_pose)
                if capture_handoff_ball_pose is not None and ball_pose is not None
                else None
            )
            capture_payload = capture.to_dict() if capture else {}
            zone_payload = zone_score.to_dict() if zone_score else {}
            first_contact_alignment = clean_rounded_number(first_contact_alignment_value)
            command_limited = bool(
                raw_command_payload
                and selected_command_payload
                and (
                    clean_rounded_number(raw_command_payload.get("linear_x"))
                    != clean_rounded_number(selected_command_payload.get("linear_x"))
                    or clean_rounded_number(raw_command_payload.get("angular_z"))
                    != clean_rounded_number(selected_command_payload.get("angular_z"))
                    or clean_rounded_number(raw_command_payload.get("target_speed_scale"))
                    != clean_rounded_number(selected_command_payload.get("target_speed_scale"))
                    or str(raw_command_payload.get("mode", "") or "")
                    != str(selected_command_payload.get("mode", "") or "")
                )
            )
            return {
                "elapsed_s": round(float(capture_elapsed_s), 6),
                "terminal_cause": str(terminal_cause or ""),
                "command_source": str(command_source or ""),
                "command_limited": command_limited,
                "command_limit_reason": str(command_limit_reason or ""),
                "selected_command": selected_command_payload,
                "raw_selected_command": raw_command_payload,
                "selected_command_mode": str(selected_command_payload.get("mode", "") or ""),
                "linear_x": clean_rounded_number(selected_command_payload.get("linear_x")),
                "angular_z": clean_rounded_number(selected_command_payload.get("angular_z")),
                "target_speed_scale": clean_rounded_number(selected_command_payload.get("target_speed_scale")),
                "capture_snapshot": capture_payload,
                "zone_snapshot": zone_payload,
                "approach_snapshot": dict(approach_snapshot or {}),
                "capture_entry_snapshot": last_capture_entry_snapshot,
                "capture_entry_diagnostics": last_capture_entry_diagnostics,
                "robot_delta_from_capture_entry_handoff_m": clean_rounded_number(robot_delta_m),
                "ball_delta_from_capture_entry_handoff_m": clean_rounded_number(ball_delta_m),
                "capture_entry_handoff_robot_pose": dict(capture_handoff_robot_pose or {}),
                "capture_entry_handoff_ball_pose": dict(capture_handoff_ball_pose or {}),
                "captured_now": bool(capture and capture.captured),
                "secure_capture_ready": bool(secure_capture_ready),
                "soft_capture_handoff_ready": bool(soft_capture_handoff_ready),
                "zone_entry_handoff_ready": bool(zone_entry_handoff_ready),
                "first_contact_alignment_seen": first_contact_alignment is not None,
                "first_contact_push_alignment_deg": first_contact_alignment,
                "ball_ahead": bool(capture_payload.get("ball_ahead", False)),
                "ball_x_m": clean_rounded_number(capture_payload.get("ball_x_m")),
                "ball_y_m": clean_rounded_number(capture_payload.get("ball_y_m")),
                "bearing_rad": clean_rounded_number(capture_payload.get("bearing_rad")),
                "within_capture_window": bool(capture_payload.get("within_capture_window", False)),
                "within_recapture_window": bool(capture_payload.get("within_recapture_window", False)),
                "zone_center_inside_zone": bool(zone_payload.get("center_inside_zone", False)),
                "zone_inside_zone": bool(zone_payload.get("inside_zone", False)),
                "entered_goal_side_before_capture": bool(entered_goal_side_before_capture),
            }

        def _append_capture_state(
            *,
            robot_pose: dict[str, Any] | None,
            ball_pose: dict[str, Any] | None,
            capture: Any = None,
            zone_score: Any = None,
            ball_motion_m: float | None = None,
            selected_command: Any = None,
            capture_diagnostics: dict[str, Any] | None = None,
            object_centric_policy: dict[str, Any] | None = None,
        ) -> None:
            append_jsonl(
                state_history_path,
                {
                    "generated_utc": utc_now(),
                    "phase": "capture",
                    "attempt": int(attempt_index),
                    "attempt_kind": str(attempt_kind),
                    "target_id": target.id,
                    "robot_pose": robot_pose,
                    "ball_pose": ball_pose,
                    "capture": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "approach_side": last_approach_snapshot,
                    "capture_entry": last_capture_entry_snapshot,
                    "capture_entry_diagnostics": last_capture_entry_diagnostics,
                    "capture_diagnostics": capture_diagnostics or {},
                    "object_centric_policy": object_centric_policy or {},
                    "selected_command": _command_payload(selected_command),
                    "ball_motion_m": ball_motion_m,
                    **self._control_debug_fields(),
                },
            )

        def _approach_result_payload(*, failure_reason: str = "") -> dict[str, Any]:
            if failure_reason:
                verdict = {"pass": False, "reason": str(failure_reason)}
            elif not enable_goal_side_stage and first_contact_alignment_value is None:
                verdict = {"pass": True, "reason": ""}
            else:
                verdict = approach_side_verdict(
                    entered_goal_side_before_capture=entered_goal_side_before_capture,
                    staging_pose_reached=staging_pose_reached_once if enable_goal_side_stage else True,
                    first_contact_push_alignment_deg=first_contact_alignment_value,
                )
            return {
                "approach_side_verdict": verdict,
                "staging_pose_reached": bool(staging_pose_reached_once if enable_goal_side_stage else True),
                "entered_goal_side_before_capture": bool(entered_goal_side_before_capture),
                "first_contact_push_alignment_deg": (
                    round(float(first_contact_alignment_value), 6)
                    if first_contact_alignment_value is not None
                    else None
                ),
                "push_direction_yaw_deg": round(float(push_direction_yaw_deg), 6),
                "stage_time_s": round(float(stage_time_s), 6),
                "capture_entry_reached": bool(capture_entry_reached_once if enable_goal_side_stage else True),
                "capture_entry_time_s": round(float(capture_entry_time_s), 6),
                "approach_failure_reason": str(failure_reason or verdict.get("reason", "") or ""),
            }
        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            _dashboard_state, robot_pose, ball_pose = self._control_loop_state(session_id=session_id, target=target)
            if handoff_robot_pose is None and isinstance(robot_pose, dict):
                handoff_robot_pose = dict(robot_pose)
            if handoff_ball_pose is None and isinstance(ball_pose, dict):
                handoff_ball_pose = dict(ball_pose)
            capture = capture_snapshot(robot_pose, ball_pose or {}, self.capture_envelope) if robot_pose and ball_pose else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
            approach_snapshot = (
                goal_side_approach_snapshot(robot_pose, ball_pose or {}, zone=self.zone)
                if robot_pose and ball_pose
                else None
            )
            ball_motion_m = pose_delta_m(previous_ball_pose, ball_pose) if previous_ball_pose is not None else None
            last_capture = capture
            last_zone_score = zone_score
            if isinstance(approach_snapshot, dict):
                last_approach_snapshot = approach_snapshot
                push_direction_yaw_deg = float(clean_number(approach_snapshot.get("push_direction_yaw_deg")) or 0.0)
                if (
                    not stage_completed
                    and not (zone_score and zone_score.center_inside_retrieval_corral)
                    and bool(approach_snapshot.get("robot_on_goal_side", False))
                ):
                    entered_goal_side_before_capture = True
                    approach_failure_reason = "entered_goal_side_before_capture"
            if (
                first_contact_alignment_value is None
                and capture
                and capture.captured
                and robot_pose
                and ball_pose
                and (capture_entry_completed or not enable_goal_side_stage)
            ):
                first_contact_alignment_value = first_contact_push_alignment_deg(robot_pose, ball_pose or {}, zone=self.zone)
            if capture and capture.captured:
                captured_started_monotonic = now_monotonic if captured_started_monotonic is None else captured_started_monotonic
            else:
                captured_started_monotonic = None
            if zone_score and zone_score.center_inside_zone:
                zone_centered_started_monotonic = (
                    now_monotonic if zone_centered_started_monotonic is None else zone_centered_started_monotonic
                )
            else:
                zone_centered_started_monotonic = None
            if not stage_completed:
                stage_command = (
                    compute_stage_command(robot_pose, ball_pose or {}, zone=self.zone)
                    if robot_pose and ball_pose
                    else None
                )
                stage_object_centric_policy: dict[str, Any] = {}
                if (
                    self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                    and robot_pose
                    and ball_pose
                ):
                    object_decision = decide_object_centric_gather_command(
                        robot_pose,
                        ball_pose or {},
                        phase="stage",
                        zone=self.zone,
                        envelope=self.capture_envelope,
                        previous_command=object_centric_previous_command,
                        previous_ball_pose=object_centric_previous_ball_pose,
                    )
                    last_object_centric_policy = dict(object_decision.diagnostics)
                    stage_object_centric_policy = last_object_centric_policy
                    if object_decision.command is not None:
                        stage_command = object_decision.command
                if stage_command is not None:
                    latest_pre_capture_command_mode = str(stage_command.mode)
                stage_ready_signal = bool(
                    isinstance(approach_snapshot, dict) and approach_snapshot.get("staging_pose_reached", False)
                ) or bool(stage_command and stage_command.mode == "stage_ready")
                if stage_command and stage_command.mode in {"stage_align", "stage_ready"}:
                    staging_pose_reached_once = True
                if stage_ready_signal:
                    staging_pose_reached_once = True
                    stage_ready_latched = True
                    stage_ready_started_monotonic = (
                        now_monotonic
                        if stage_ready_started_monotonic is None
                        else stage_ready_started_monotonic
                    )
                elif not stage_ready_latched:
                    stage_ready_started_monotonic = None
                stage_manager_decision = decide_gather_manager_directive(
                    GatherManagerState(
                        phase="stage",
                        phase_elapsed_s=now_monotonic - float(stage_started_monotonic or now_monotonic),
                        approach_snapshot=approach_snapshot or {},
                        capture_snapshot=capture.to_dict() if capture else {},
                        phase_ready_observed=stage_ready_signal,
                        phase_ready_latched=stage_ready_latched,
                        attempt_kind=attempt_kind,
                        latest_command_mode=latest_pre_capture_command_mode,
                    )
                )
                if stage_manager_decision.directive == "recover_goal_side":
                    stage_ready_latched = False
                    stage_ready_started_monotonic = None
                elif stage_ready_latched:
                    # Hold the first valid stage-ready pose steady so the capture-entry
                    # handoff starts from the same geometry that satisfied staging.
                    stage_command = PlaceControlCommand(
                        mode="stage_ready",
                        linear_x=0.0,
                        angular_z=0.0,
                        target_speed_scale=0.0,
                        rationale="Hold the first valid staging pose steady until capture entry begins.",
                    )
                    latest_pre_capture_command_mode = str(stage_command.mode)
                    if stage_object_centric_policy:
                        stage_object_centric_policy = {
                            **stage_object_centric_policy,
                            "selected_command": stage_command.to_dict(),
                            "mode": str(stage_command.mode),
                        }
                        last_object_centric_policy = dict(stage_object_centric_policy)
                self._update_gather_runtime_state(
                    mission_phase="stage",
                    gather_phase="stage",
                    capture_state=capture.to_dict() if capture else {},
                    zone_score=zone_score.to_dict() if zone_score else {},
                    latest_feedback=f"Staging behind {target.label} before first contact.",
                )
                self._update_visit_runtime_state(
                    proof_state="capturing",
                    mission_phase="stage",
                    latest_feedback=f"Staging behind {target.label} before first contact.",
                )
                append_jsonl(
                    state_history_path,
                    {
                        "generated_utc": utc_now(),
                        "phase": "stage",
                        "attempt": int(attempt_index),
                        "attempt_kind": str(attempt_kind),
                        "target_id": target.id,
                        "robot_pose": robot_pose,
                        "ball_pose": ball_pose,
                        "capture": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "approach_side": approach_snapshot or {},
                        "manager_directive": stage_manager_decision.directive,
                        "selected_command": stage_command.to_dict() if stage_command else {},
                        "object_centric_policy": stage_object_centric_policy,
                        "ball_motion_m": ball_motion_m,
                        **self._control_debug_fields(),
                    },
                )
                if (
                    stage_ready_latched
                    and stage_manager_decision.directive == "close_capture_gap"
                    and
                    stage_ready_started_monotonic is not None
                    and (now_monotonic - stage_ready_started_monotonic) >= DEFAULT_STAGE_READY_DWELL_S
                ):
                    stage_completed = True
                    stage_ready_latched = False
                    stage_time_s = now_monotonic - float(stage_started_monotonic or now_monotonic)
                    capture_entry_started_monotonic = now_monotonic
                    capture_entry_ready_started_monotonic = None
                    capture_entry_ready_latched = False
                    self._set_manual_drive(
                        enabled=False,
                        mode="stage_ready",
                        rationale="Robot is staged behind the ball; handing off to capture.",
                    )
                    self._update_gather_runtime_state(
                        latest_feedback=f"Staged behind {target.label}; starting capture.",
                    )
                    previous_ball_pose = dict(ball_pose or {}) if ball_pose else previous_ball_pose
                    time.sleep(self.args.poll_s)
                    continue
                if (
                    stage_started_monotonic is not None
                    and (now_monotonic - stage_started_monotonic) >= stage_timeout_s
                    and not stage_ready_latched
                ):
                    stage_time_s = now_monotonic - float(stage_started_monotonic)
                    if not approach_failure_reason:
                        approach_failure_reason = (
                            "staging_pose_not_reached"
                            if not staging_pose_reached_once
                            else "goal_side_stage_timeout"
                        )
                    self._set_manual_drive(
                        enabled=False,
                        mode="stage_timeout",
                        rationale="Goal-side staging timed out before first contact.",
                    )
                    timeout_payload = {
                        "failure_reason": "goal_side_stage_timeout",
                        "failure_stage": "stage",
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "object_centric_policy": last_object_centric_policy,
                        **_approach_result_payload(failure_reason=approach_failure_reason),
                    }
                    write_json(mission_root / f"{target.id}_stage_timeout.json", timeout_payload)
                    return False, timeout_payload
                if stage_command is not None:
                    self._set_manual_drive(
                        enabled=True,
                        linear_x=stage_command.linear_x,
                        angular_z=stage_command.angular_z,
                        mode=stage_command.mode,
                        rationale=stage_command.rationale,
                    )
                    self._update_gather_runtime_state(latest_control_command=stage_command.to_dict())
                    if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                        object_centric_previous_command = stage_command
                if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                    object_centric_previous_ball_pose = dict(ball_pose or {}) if ball_pose else object_centric_previous_ball_pose
                previous_ball_pose = dict(ball_pose or {}) if ball_pose else previous_ball_pose
                time.sleep(self.args.poll_s)
                continue
            if enable_goal_side_stage and not capture_entry_completed:
                capture_entry_snapshot_payload = (
                    capture_entry_snapshot(
                        robot_pose,
                        ball_pose or {},
                        zone=self.zone,
                        envelope=self.capture_envelope,
                    )
                    if robot_pose and ball_pose
                    else None
                )
                capture_entry_ready_signal = bool(
                    isinstance(capture_entry_snapshot_payload, dict)
                    and capture_entry_snapshot_payload.get("capture_entry_reached", False)
                )
                if capture_entry_ready_signal:
                    capture_entry_reached_once = True
                    capture_entry_ready_latched = True
                    capture_entry_ready_started_monotonic = (
                        now_monotonic
                        if capture_entry_ready_started_monotonic is None
                        else capture_entry_ready_started_monotonic
                    )
                elif not capture_entry_ready_latched:
                    capture_entry_ready_started_monotonic = None
                capture_entry_command = (
                    compute_capture_entry_command(
                        robot_pose,
                        ball_pose or {},
                        zone=self.zone,
                        envelope=self.capture_envelope,
                    )
                    if robot_pose and ball_pose
                    else None
                )
                capture_entry_object_centric_policy: dict[str, Any] = {}
                if (
                    self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                    and robot_pose
                    and ball_pose
                ):
                    object_decision = decide_object_centric_gather_command(
                        robot_pose,
                        ball_pose or {},
                        phase="capture_entry",
                        zone=self.zone,
                        envelope=self.capture_envelope,
                        previous_command=object_centric_previous_command,
                        previous_ball_pose=object_centric_previous_ball_pose,
                    )
                    last_object_centric_policy = dict(object_decision.diagnostics)
                    capture_entry_object_centric_policy = last_object_centric_policy
                    if object_decision.command is not None:
                        capture_entry_command = object_decision.command
                if capture_entry_command is not None:
                    latest_pre_capture_command_mode = str(capture_entry_command.mode)
                capture_entry_manager_decision = decide_gather_manager_directive(
                    GatherManagerState(
                        phase="capture_entry",
                        phase_elapsed_s=now_monotonic - float(capture_entry_started_monotonic or now_monotonic),
                        approach_snapshot=approach_snapshot or {},
                        capture_snapshot=capture.to_dict() if capture else {},
                        capture_entry_snapshot=capture_entry_snapshot_payload or {},
                        phase_ready_observed=capture_entry_ready_signal,
                        phase_ready_latched=capture_entry_ready_latched,
                        attempt_kind=attempt_kind,
                        latest_command_mode=latest_pre_capture_command_mode,
                    )
                )
                capture_entry_diagnostics_payload = _capture_entry_diagnostics_payload(
                    now_monotonic=now_monotonic,
                    snapshot=capture_entry_snapshot_payload,
                    ready_signal=capture_entry_ready_signal,
                    manager_directive=capture_entry_manager_decision.directive,
                    selected_command=capture_entry_command,
                    robot_pose=robot_pose,
                    ball_pose=ball_pose,
                )
                last_capture_entry_snapshot = dict(capture_entry_snapshot_payload or {})
                last_capture_entry_diagnostics = dict(capture_entry_diagnostics_payload)
                if capture_entry_manager_decision.directive == "recover_goal_side":
                    capture_entry_ready_latched = False
                    capture_entry_ready_started_monotonic = None
                    entered_goal_side_before_capture = True
                    approach_failure_reason = "capture_entry_goal_side_loss"
                    capture_entry_diagnostics_payload = _capture_entry_diagnostics_payload(
                        now_monotonic=now_monotonic,
                        snapshot=capture_entry_snapshot_payload,
                        ready_signal=capture_entry_ready_signal,
                        manager_directive=capture_entry_manager_decision.directive,
                        selected_command=capture_entry_command,
                        robot_pose=robot_pose,
                        ball_pose=ball_pose,
                    )
                    last_capture_entry_diagnostics = dict(capture_entry_diagnostics_payload)
                    self._set_manual_drive(
                        enabled=False,
                        mode="capture_entry_goal_side_loss",
                        rationale="Robot crossed back onto the goal side before the capture-entry corridor was reached.",
                    )
                    failure_payload = {
                        "failure_reason": "capture_entry_goal_side_loss",
                        "failure_stage": "capture_entry",
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "capture_entry_snapshot": last_capture_entry_snapshot,
                        "capture_entry_diagnostics": last_capture_entry_diagnostics,
                        "object_centric_policy": last_object_centric_policy,
                        **_approach_result_payload(failure_reason=approach_failure_reason),
                    }
                    write_json(mission_root / f"{target.id}_capture_entry_goal_side_loss.json", failure_payload)
                    return False, failure_payload
                self._update_gather_runtime_state(
                    mission_phase="capture_entry",
                    gather_phase="capture_entry",
                    capture_state=capture.to_dict() if capture else {},
                    zone_score=zone_score.to_dict() if zone_score else {},
                    latest_feedback=f"Closing the final capture gap on {target.label}.",
                )
                self._update_visit_runtime_state(
                    proof_state="capturing",
                    mission_phase="capture_entry",
                    latest_feedback=f"Closing the final capture gap on {target.label}.",
                )
                append_jsonl(
                    state_history_path,
                    {
                        "generated_utc": utc_now(),
                        "phase": "capture_entry",
                        "attempt": int(attempt_index),
                        "attempt_kind": str(attempt_kind),
                        "target_id": target.id,
                        "robot_pose": robot_pose,
                        "ball_pose": ball_pose,
                        "capture": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "approach_side": approach_snapshot or {},
                        "capture_entry": capture_entry_snapshot_payload or {},
                        "capture_entry_diagnostics": capture_entry_diagnostics_payload,
                        "manager_directive": capture_entry_manager_decision.directive,
                        "selected_command": capture_entry_command.to_dict() if capture_entry_command else {},
                        "object_centric_policy": capture_entry_object_centric_policy,
                        "ball_motion_m": ball_motion_m,
                        **self._control_debug_fields(),
                    },
                )
                if (
                    capture_entry_ready_latched
                    and capture_entry_manager_decision.directive == "handoff_to_capture"
                    and
                    capture_entry_ready_started_monotonic is not None
                    and (now_monotonic - capture_entry_ready_started_monotonic) >= DEFAULT_CAPTURE_ENTRY_READY_DWELL_S
                ):
                    capture_entry_completed = True
                    capture_entry_ready_latched = False
                    capture_entry_time_s = now_monotonic - float(capture_entry_started_monotonic or now_monotonic)
                    capture_started_monotonic = now_monotonic
                    capture_handoff_robot_pose = dict(robot_pose or {}) if isinstance(robot_pose, dict) else None
                    capture_handoff_ball_pose = dict(ball_pose or {}) if isinstance(ball_pose, dict) else None
                    self._set_manual_drive(
                        enabled=False,
                        mode="capture_entry_ready",
                        rationale="Ball reached the capture-entry corridor; handing off to generic capture.",
                    )
                    self._update_gather_runtime_state(
                        latest_feedback=f"Capture entry closed on {target.label}; starting generic capture.",
                    )
                    previous_ball_pose = dict(ball_pose or {}) if ball_pose else previous_ball_pose
                    time.sleep(self.args.poll_s)
                    continue
                if (
                    capture_entry_started_monotonic is not None
                    and (now_monotonic - capture_entry_started_monotonic) >= DEFAULT_CAPTURE_ENTRY_TIMEOUT_S
                    and not capture_entry_ready_latched
                ):
                    capture_entry_time_s = now_monotonic - float(capture_entry_started_monotonic)
                    if not approach_failure_reason:
                        approach_failure_reason = "capture_entry_timeout"
                    self._set_manual_drive(
                        enabled=False,
                        mode="capture_entry_timeout",
                        rationale="Capture-entry corridor timed out before generic capture could start.",
                    )
                    timeout_payload = {
                        "failure_reason": "capture_entry_timeout",
                        "failure_stage": "capture_entry",
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "capture_entry_snapshot": last_capture_entry_snapshot,
                        "capture_entry_diagnostics": last_capture_entry_diagnostics,
                        "object_centric_policy": last_object_centric_policy,
                        **_approach_result_payload(failure_reason=approach_failure_reason),
                    }
                    write_json(mission_root / f"{target.id}_capture_entry_timeout.json", timeout_payload)
                    return False, timeout_payload
                if capture_entry_command is not None:
                    self._set_manual_drive(
                        enabled=True,
                        linear_x=capture_entry_command.linear_x,
                        angular_z=capture_entry_command.angular_z,
                        mode=capture_entry_command.mode,
                        rationale=capture_entry_command.rationale,
                    )
                    self._update_gather_runtime_state(latest_control_command=capture_entry_command.to_dict())
                    if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                        object_centric_previous_command = capture_entry_command
                if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                    object_centric_previous_ball_pose = dict(ball_pose or {}) if ball_pose else object_centric_previous_ball_pose
                previous_ball_pose = dict(ball_pose or {}) if ball_pose else previous_ball_pose
                time.sleep(self.args.poll_s)
                continue
            self._update_gather_runtime_state(
                mission_phase="capture",
                gather_phase="capture",
                capture_state=capture.to_dict() if capture else {},
                zone_score=zone_score.to_dict() if zone_score else {},
                latest_feedback=f"Capturing {target.label}.",
            )
            self._update_visit_runtime_state(
                proof_state="capturing",
                mission_phase="capture",
                latest_feedback=f"Capturing {target.label}.",
            )
            if ball_pose:
                self._update_prior_from_ball_pose(target.id, ball_pose)
            if capture_started_monotonic is None:
                capture_started_monotonic = now_monotonic
            if capture_handoff_robot_pose is None and isinstance(robot_pose, dict):
                capture_handoff_robot_pose = dict(robot_pose)
            if capture_handoff_ball_pose is None and isinstance(ball_pose, dict):
                capture_handoff_ball_pose = dict(ball_pose)
            command = None
            raw_command = None
            command_source = "no_pose_or_ball"
            command_limit_reason = ""
            capture_object_centric_policy: dict[str, Any] = {}
            if (
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and robot_pose
                and ball_pose
            ):
                object_decision = decide_object_centric_gather_command(
                    robot_pose,
                    ball_pose or {},
                    phase="capture",
                    zone=self.zone,
                    envelope=self.capture_envelope,
                    previous_command=object_centric_previous_command,
                    previous_ball_pose=object_centric_previous_ball_pose,
                )
                command = object_decision.command
                raw_command = object_decision.raw_command
                last_object_centric_policy = dict(object_decision.diagnostics)
                capture_object_centric_policy = last_object_centric_policy
                command_source = "object_centric_policy"
                command_limit_reason = str(capture_object_centric_policy.get("guard_rejection_reason", "") or "")
            zone_entry_handoff_ready = bool(
                zone_score
                and zone_score.center_inside_zone
                and zone_centered_started_monotonic is not None
                and (now_monotonic - zone_centered_started_monotonic) >= 0.5
                and (
                    ball_motion_m is None
                    or ball_motion_m <= max(DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M * 2.0, 0.02)
                )
            )
            secure_capture_ready = bool(secure_capture(capture, self.capture_envelope))
            if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                secure_capture_ready = bool(
                    secure_capture_ready
                    and command is not None
                    and str(getattr(command, "mode", "") or "") == "captured"
                )
            soft_capture_handoff_ready = bool(
                self.gather_control_family != OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.captured
                and captured_started_monotonic is not None
                and (now_monotonic - captured_started_monotonic) >= 0.5
                and float(capture.ball_x_m) <= 0.35
            )
            if zone_entry_handoff_ready:
                terminal_command = {
                    "mode": "capture_handoff",
                    "linear_x": 0.0,
                    "angular_z": 0.0,
                    "target_speed_scale": 0.0,
                    "rationale": "Ball reached zone during capture; handing off to place verification.",
                }
                last_capture_diagnostics = _capture_diagnostics_payload(
                    now_monotonic=now_monotonic,
                    capture=capture,
                    zone_score=zone_score,
                    approach_snapshot=approach_snapshot or {},
                    selected_command=terminal_command,
                    raw_command=terminal_command,
                    command_source="terminal",
                    robot_pose=robot_pose,
                    ball_pose=ball_pose,
                    zone_entry_handoff_ready=zone_entry_handoff_ready,
                    secure_capture_ready=secure_capture_ready,
                    soft_capture_handoff_ready=soft_capture_handoff_ready,
                    terminal_cause="zone_entry",
                )
                _append_capture_state(
                    robot_pose=robot_pose,
                    ball_pose=ball_pose,
                    capture=capture,
                    zone_score=zone_score,
                    ball_motion_m=ball_motion_m,
                    selected_command=terminal_command,
                    capture_diagnostics=last_capture_diagnostics,
                    object_centric_policy=last_object_centric_policy,
                )
                self._set_manual_drive(False, mode="capture_handoff", rationale="Ball reached zone during capture; handing off to place verification.")
                return True, {
                    "capture_state": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "entered_zone_during_capture": True,
                    "handoff_kind": "zone_entry",
                    "capture_diagnostics": last_capture_diagnostics,
                    "object_centric_policy": last_object_centric_policy,
                    **_approach_result_payload(),
                }
            if secure_capture_ready:
                terminal_command = {
                    "mode": "captured",
                    "linear_x": 0.0,
                    "angular_z": 0.0,
                    "target_speed_scale": 0.0,
                    "rationale": "Ball captured.",
                }
                last_capture_diagnostics = _capture_diagnostics_payload(
                    now_monotonic=now_monotonic,
                    capture=capture,
                    zone_score=zone_score,
                    approach_snapshot=approach_snapshot or {},
                    selected_command=terminal_command,
                    raw_command=terminal_command,
                    command_source="terminal",
                    robot_pose=robot_pose,
                    ball_pose=ball_pose,
                    zone_entry_handoff_ready=zone_entry_handoff_ready,
                    secure_capture_ready=secure_capture_ready,
                    soft_capture_handoff_ready=soft_capture_handoff_ready,
                    terminal_cause="secure_capture",
                )
                _append_capture_state(
                    robot_pose=robot_pose,
                    ball_pose=ball_pose,
                    capture=capture,
                    zone_score=zone_score,
                    ball_motion_m=ball_motion_m,
                    selected_command=terminal_command,
                    capture_diagnostics=last_capture_diagnostics,
                    object_centric_policy=last_object_centric_policy,
                )
                self._set_manual_drive(False, mode="captured", rationale="Ball captured.")
                return True, {
                    "capture_state": capture.to_dict(),
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "handoff_kind": "secure_capture",
                    "capture_diagnostics": last_capture_diagnostics,
                    "object_centric_policy": last_object_centric_policy,
                    **_approach_result_payload(),
                }
            if soft_capture_handoff_ready:
                terminal_command = {
                    "mode": "capture_handoff",
                    "linear_x": 0.0,
                    "angular_z": 0.0,
                    "target_speed_scale": 0.0,
                    "rationale": "Ball is stably inside the spur; handing off to place control.",
                }
                last_capture_diagnostics = _capture_diagnostics_payload(
                    now_monotonic=now_monotonic,
                    capture=capture,
                    zone_score=zone_score,
                    approach_snapshot=approach_snapshot or {},
                    selected_command=terminal_command,
                    raw_command=terminal_command,
                    command_source="terminal",
                    robot_pose=robot_pose,
                    ball_pose=ball_pose,
                    zone_entry_handoff_ready=zone_entry_handoff_ready,
                    secure_capture_ready=secure_capture_ready,
                    soft_capture_handoff_ready=soft_capture_handoff_ready,
                    terminal_cause="soft_capture",
                )
                _append_capture_state(
                    robot_pose=robot_pose,
                    ball_pose=ball_pose,
                    capture=capture,
                    zone_score=zone_score,
                    ball_motion_m=ball_motion_m,
                    selected_command=terminal_command,
                    capture_diagnostics=last_capture_diagnostics,
                    object_centric_policy=last_object_centric_policy,
                )
                self._set_manual_drive(False, mode="capture_handoff", rationale="Ball is stably inside the spur; handing off to place control.")
                return True, {
                    "capture_state": capture.to_dict(),
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "soft_capture_handoff": True,
                    "handoff_kind": "soft_capture",
                    "capture_diagnostics": last_capture_diagnostics,
                    "object_centric_policy": last_object_centric_policy,
                    **_approach_result_payload(),
                }
            handoff_near_zone_control = False
            if robot_pose and ball_pose:
                handoff_near_zone_control = bool(
                    not prefer_zone_recovery
                    and capture
                    and capture.ball_ahead
                    and zone_score is not None
                    and float(zone_score.zone_distance_m) <= (float(self.zone.control_radius_m) + 0.35)
                )
                if self.gather_control_family != OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                    if prefer_zone_recovery:
                        use_zone_recovery = bool(
                            capture
                            and capture.ball_ahead
                            and (
                                capture.within_recapture_window
                                or (
                                    zone_score is not None
                                    and float(zone_score.zone_distance_m) <= (float(self.zone.control_radius_m) + 0.35)
                                )
                            )
                        )
                        if use_zone_recovery:
                            command = compute_place_command(
                                robot_pose,
                                ball_pose or {},
                                zone=self.zone,
                                envelope=self.capture_envelope,
                            )
                            command_source = "place_recapture"
                        else:
                            command = compute_capture_command(robot_pose, ball_pose or {}, envelope=self.capture_envelope)
                            command_source = "capture_fallback"
                    elif handoff_near_zone_control:
                        command = compute_place_command(
                            robot_pose,
                            ball_pose or {},
                            zone=self.zone,
                            envelope=self.capture_envelope,
                        )
                        command_source = "near_zone_place_handoff"
                    else:
                        command = compute_capture_command(robot_pose, ball_pose or {}, envelope=self.capture_envelope)
                        command_source = "capture_command"
                if raw_command is None:
                    raw_command = command
            if (
                self.gather_control_family != OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and prefer_zone_recovery
                and command is not None
            ):
                angular_limit = 0.50
                linear_limit = 0.055
                rationale = "Keep the ball local during post-place recapture instead of driving through it."
                if capture and not capture.ball_ahead:
                    linear_limit = 0.0
                    angular_limit = 0.90
                    rationale = "Ball slipped behind after place; turn in place quickly before it leaves local recovery range."
                elif capture and capture.within_recapture_window:
                    if float(capture.ball_x_m) > 0.40 or abs(float(capture.ball_y_m)) > 0.08:
                        linear_limit = 0.0
                        angular_limit = 0.35
                        rationale = "Ball is ahead but not seated; rotate under it before nudging forward again."
                    elif float(capture.ball_x_m) > 0.34:
                        linear_limit = 0.015
                        angular_limit = 0.40
                elif capture:
                    linear_limit = 0.02
                    angular_limit = 0.65
                    rationale = "Ball is still local but outside the spur mouth; bias toward turning before chasing forward."
                command = command.__class__(
                    mode="place_recapture_hold" if capture and capture.within_recapture_window else command.mode,
                    linear_x=min(float(command.linear_x), linear_limit),
                    angular_z=clamp(float(command.angular_z), -angular_limit, angular_limit),
                    target_speed_scale=min(float(command.target_speed_scale), 0.55 if linear_limit > 0.02 else 0.35),
                    rationale=rationale,
                )
                command_limit_reason = rationale
            elif (
                self.gather_control_family != OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and handoff_near_zone_control
                and command is not None
            ):
                linear_limit = 0.03
                angular_limit = 0.35
                rationale = "Near the corral, switch to a gentle handoff instead of driving through the ball."
                if zone_score and zone_score.center_inside_zone:
                    linear_limit = 0.0
                    angular_limit = 0.25
                    rationale = "Ball is already centered in the corral; stop and let friction settle it."
                elif zone_score and zone_score.inside_zone:
                    linear_limit = 0.012
                    angular_limit = 0.30
                    rationale = "Ball is already inside the corral overlap; creep only if needed."
                elif capture and capture.within_recapture_window and (
                    float(capture.ball_x_m) > 0.36 or abs(float(capture.ball_y_m)) > 0.06
                ):
                    linear_limit = 0.0
                    angular_limit = 0.30
                    rationale = "Ball is near the corral but not seated; hold and yaw gently before the final settle."
                command = command.__class__(
                    mode="capture_handoff_hold" if capture and capture.within_recapture_window else command.mode,
                    linear_x=min(float(command.linear_x), linear_limit),
                    angular_z=clamp(float(command.angular_z), -angular_limit, angular_limit),
                    target_speed_scale=min(float(command.target_speed_scale), 0.45 if linear_limit > 0.015 else 0.30),
                    rationale=rationale,
                )
                command_limit_reason = rationale
            last_capture_diagnostics = _capture_diagnostics_payload(
                now_monotonic=now_monotonic,
                capture=capture,
                zone_score=zone_score,
                approach_snapshot=approach_snapshot or {},
                selected_command=command,
                raw_command=raw_command,
                command_source=command_source,
                command_limit_reason=command_limit_reason,
                robot_pose=robot_pose,
                ball_pose=ball_pose,
                zone_entry_handoff_ready=zone_entry_handoff_ready,
                secure_capture_ready=secure_capture_ready,
                soft_capture_handoff_ready=soft_capture_handoff_ready,
            )
            _append_capture_state(
                robot_pose=robot_pose,
                ball_pose=ball_pose,
                capture=capture,
                zone_score=zone_score,
                ball_motion_m=ball_motion_m,
                selected_command=command,
                capture_diagnostics=last_capture_diagnostics,
                object_centric_policy=capture_object_centric_policy,
            )
            if command is not None:
                self._set_manual_drive(
                    True,
                    linear_x=command.linear_x,
                    angular_z=command.angular_z,
                    mode=command.mode,
                    rationale=command.rationale,
                )
                self._update_gather_runtime_state(latest_control_command=command.to_dict())
                if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                    object_centric_previous_command = command
            if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                object_centric_previous_ball_pose = dict(ball_pose or {}) if ball_pose else object_centric_previous_ball_pose
            previous_ball_pose = dict(ball_pose or {}) if ball_pose else previous_ball_pose
            time.sleep(self.args.poll_s)

        self._set_manual_drive(False, mode="capture_timeout", rationale="Capture timed out.")
        last_capture_payload = last_capture.to_dict() if last_capture else {}
        last_zone_payload = last_zone_score.to_dict() if last_zone_score else {}
        timeout_capture_diagnostics = dict(last_capture_diagnostics)
        timeout_capture_diagnostics["terminal_cause"] = "capture_timeout"
        last_capture_diagnostics = timeout_capture_diagnostics
        correction_eligible = zone_edge_correction_eligible(
            capture=last_capture,
            zone_score=last_zone_score,
            zone=self.zone,
        )
        timeout_payload = {
            "failure_reason": "capture_timeout",
            "failure_stage": "capture",
            "capture_state": last_capture_payload,
            "zone_score": last_zone_payload,
            "zone_edge_correction_eligible": bool(correction_eligible),
            "allow_full_revisit": False,
            "capture_entry_snapshot": last_capture_entry_snapshot,
            "capture_entry_diagnostics": last_capture_entry_diagnostics,
            "capture_diagnostics": last_capture_diagnostics,
            "object_centric_policy": last_object_centric_policy,
            **_approach_result_payload(failure_reason=approach_failure_reason),
        }
        write_json(mission_root / f"{target.id}_capture_timeout.json", timeout_payload)
        return False, timeout_payload

    def _place_target(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
        state_history_path: Path,
        attempt_index: int = 0,
        attempt_kind: str = "",
    ) -> tuple[bool, dict[str, Any]]:
        place_timeout_budget_s = max(self.args.place_timeout_s, 0.1)
        if (
            self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
            and place_timeout_budget_s >= 30.0
        ):
            place_timeout_budget_s = max(place_timeout_budget_s, DEFAULT_OBJECT_CENTRIC_PLACE_TIMEOUT_S)
        deadline = time.monotonic() + place_timeout_budget_s
        last_captured_monotonic: float | None = None
        local_recovery_attempted = False
        local_recovery_started_monotonic: float | None = None
        recaptured_settle_started_monotonic: float | None = None
        release_origin_monotonic: float | None = None
        release_monitoring_active = False
        release_samples: list[dict[str, Any]] = []
        release_prev_ball_pose: dict[str, Any] | None = None
        release_recontact_count = 0
        release_inside_seen = False
        marginal_capture_started_monotonic: float | None = None
        zone_edge_correction_started_monotonic: float | None = None
        escaped_zone_correction_started_monotonic: float | None = None
        stop_capture_state: dict[str, Any] = {}
        stopped_with_ball_captured = False
        release_capture_state: dict[str, Any] = {}
        release_started_with_capture = False
        zone_edge_correction_count = 0
        retrieval_centered_started_monotonic: float | None = None
        control_centered_started_monotonic: float | None = None
        pre_release_still_started_monotonic: float | None = None
        recent_ball_motion_samples: list[float] = []
        settle_no_chase_active = False
        settle_no_chase_activated = False
        settle_no_chase_exit_started_monotonic: float | None = None
        settle_no_chase_exit_reason = "none"
        release_gate_blocked_reason = "none"
        stationary_recapture_signature: tuple[float, float, float] | None = None
        stationary_recapture_started_monotonic: float | None = None
        object_centric_place_previous_command: PlaceControlCommand | None = None
        object_centric_place_previous_ball_pose: dict[str, Any] | None = None

        def _record_stop_capture(current_capture: Any) -> None:
            nonlocal stop_capture_state
            nonlocal stopped_with_ball_captured
            stop_capture_state = current_capture.to_dict() if current_capture else {}
            stopped_with_ball_captured = secure_capture(current_capture, self.capture_envelope)

        def _record_release_capture(current_capture: Any) -> None:
            nonlocal release_capture_state
            nonlocal release_started_with_capture
            release_capture_state = current_capture.to_dict() if current_capture else {}
            release_started_with_capture = secure_capture(current_capture, self.capture_envelope)

        def _retention_fields() -> dict[str, Any]:
            return {
                "stopped_with_ball_captured": bool(stopped_with_ball_captured),
                "release_started_with_capture": bool(release_started_with_capture),
                "stop_capture_state": dict(stop_capture_state),
                "release_capture_state": dict(release_capture_state),
            }

        def _settle_no_chase_fields() -> dict[str, Any]:
            return {
                "settle_no_chase_activated": bool(settle_no_chase_activated),
                "settle_no_chase_exit_reason": clean_text(settle_no_chase_exit_reason, "none"),
                "release_gate_blocked_reason": clean_text(release_gate_blocked_reason, "none"),
            }

        def _place_diagnostics(
            *,
            current_capture: Any = None,
            current_zone_score: Any = None,
            allow_full_revisit: bool | None = None,
        ) -> dict[str, Any]:
            correction_eligible = zone_edge_correction_eligible(
                capture=current_capture,
                zone_score=current_zone_score,
                zone=self.zone,
            )
            return {
                "zone_edge_correction_count": int(zone_edge_correction_count),
                "zone_edge_correction_eligible": bool(correction_eligible),
                "allow_full_revisit": (
                    not bool(correction_eligible)
                    if allow_full_revisit is None
                    else bool(allow_full_revisit)
                ),
            }

        def _local_settle_correction_eligible(
            *,
            current_capture: Any = None,
            current_zone_score: Any = None,
        ) -> bool:
            if current_zone_score and bool(current_zone_score.inside_retrieval_corral):
                return True
            return bool(
                current_capture
                and current_capture.within_recapture_window
                and current_zone_score
                and float(current_zone_score.zone_distance_m)
                <= (float(self.zone.retrieval_radius_m) + 0.12)
            )

        def _settle_metrics() -> dict[str, Any]:
            return summarize_release_settle_trace(
                surface_profile=self.surface_profile,
                zone=self.zone,
                release_samples=release_samples,
                release_recontact_count=release_recontact_count,
            ).to_dict()

        def _settle_fields(metrics: dict[str, Any] | None = None) -> dict[str, Any]:
            active_metrics = metrics if isinstance(metrics, dict) else _settle_metrics()
            return {
                "final_inside_retrieval_corral": bool(active_metrics.get("final_inside_retrieval_corral", False)),
                "final_center_inside_zone": bool(active_metrics.get("final_center_inside_zone", False)),
                "ball_stopped_in_corral": bool(active_metrics.get("ball_stopped_in_corral", False)),
                "rolled_away_after_release": bool(active_metrics.get("rolled_away_after_release", False)),
                "settled_in_corral_pass": bool(active_metrics.get("settled_in_corral_pass", False)),
                "settle_exit_reason": clean_text(active_metrics.get("settle_exit_reason")),
            }

        def _settle_monitor_ready(
            *,
            current_capture: Any = None,
            current_zone_score: Any = None,
            ball_motion_m: float | None = None,
            now_monotonic: float,
        ) -> bool:
            if not current_zone_score or not bool(current_zone_score.center_inside_retrieval_corral):
                return False
            if bool(current_zone_score.center_inside_zone):
                corridor_ready = True
            else:
                corridor_ready = float(current_zone_score.zone_distance_m) <= max(
                    float(self.zone.control_radius_m) + 0.20,
                    float(self.zone.retrieval_radius_m) - 0.10,
                )
            if not corridor_ready:
                return False
            dwell_started = (
                control_centered_started_monotonic
                if bool(current_zone_score.center_inside_zone)
                else retrieval_centered_started_monotonic
            )
            if dwell_started is None or (now_monotonic - dwell_started) < 0.5:
                return False
            if current_capture and (current_capture.captured or current_capture.within_recapture_window):
                required_still_s = 0.5
            else:
                required_still_s = DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
            if (
                pre_release_still_started_monotonic is None
                or (now_monotonic - pre_release_still_started_monotonic) < required_still_s
            ):
                return False
            if current_capture and (current_capture.captured or current_capture.within_recapture_window):
                return ball_motion_m is None or ball_motion_m <= max(DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M * 2.0, 0.02)
            return ball_motion_m is not None and ball_motion_m <= DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M

        def _motion_trending_slower() -> bool:
            if len(recent_ball_motion_samples) < 3:
                return False
            oldest = float(recent_ball_motion_samples[0])
            newest = float(recent_ball_motion_samples[-1])
            return newest <= max(oldest * 0.75, oldest - 0.01)

        def _settle_no_chase_ready(
            *,
            current_capture: Any = None,
            current_zone_score: Any = None,
            ball_motion_m: float | None = None,
            now_monotonic: float,
        ) -> bool:
            if not current_zone_score or not bool(current_zone_score.center_inside_retrieval_corral):
                return False
            object_centric_family = self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
            if object_centric_family and current_capture and not current_capture.ball_ahead:
                return False
            object_centric_unsecured = bool(
                object_centric_family
                and current_capture
                and current_capture.ball_ahead
                and not current_capture.captured
            )
            if object_centric_unsecured:
                unsecured_still_dwell_ready = bool(
                    pre_release_still_started_monotonic is not None
                    and (now_monotonic - pre_release_still_started_monotonic)
                    >= DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S
                )
                if (
                    float(current_zone_score.zone_distance_m)
                    <= DEFAULT_OBJECT_CENTRIC_UNSECURE_MOVING_SETTLE_ZONE_MAX_M
                    and bool(current_zone_score.center_inside_zone)
                    and retrieval_centered_started_monotonic is not None
                    and (now_monotonic - retrieval_centered_started_monotonic)
                    >= DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S
                    and ball_motion_m is not None
                    and ball_motion_m <= DEFAULT_SETTLE_NO_CHASE_MOTION_TOLERANCE_M
                    and unsecured_still_dwell_ready
                ):
                    return True
                if (
                    bool(current_zone_score.center_inside_zone)
                    and float(current_zone_score.zone_distance_m)
                    <= DEFAULT_OBJECT_CENTRIC_UNSECURE_CENTER_ROLLTHROUGH_ZONE_MAX_M
                    and retrieval_centered_started_monotonic is not None
                    and (now_monotonic - retrieval_centered_started_monotonic)
                    >= DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S
                    and control_centered_started_monotonic is not None
                    and (now_monotonic - control_centered_started_monotonic)
                    >= DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S
                    and ball_motion_m is not None
                    and ball_motion_m <= DEFAULT_OBJECT_CENTRIC_UNSECURE_CENTER_ROLLTHROUGH_MOTION_MAX_M
                    and unsecured_still_dwell_ready
                    and float(current_capture.ball_x_m) >= DEFAULT_OBJECT_CENTRIC_UNSECURE_CENTER_ROLLTHROUGH_MIN_X_M
                    and abs(float(current_capture.ball_y_m))
                    <= DEFAULT_OBJECT_CENTRIC_UNSECURE_CENTER_ROLLTHROUGH_MAX_LATERAL_M
                ):
                    return True
                if (
                    not bool(current_zone_score.center_inside_zone)
                    and float(current_zone_score.zone_distance_m)
                    <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_ZONE_MAX_M
                    and retrieval_centered_started_monotonic is not None
                    and (now_monotonic - retrieval_centered_started_monotonic)
                    >= DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S
                    and ball_motion_m is not None
                    and ball_motion_m <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MOTION_MAX_M
                    and unsecured_still_dwell_ready
                    and float(current_capture.ball_x_m) >= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MIN_X_M
                    and float(current_capture.ball_x_m) <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MAX_X_M
                    and abs(float(current_capture.ball_y_m))
                    >= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MIN_LATERAL_M
                    and abs(float(current_capture.ball_y_m))
                    <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_SHOULDER_MAX_LATERAL_M
                ):
                    return True
                if (
                    not bool(current_zone_score.center_inside_zone)
                    and float(current_zone_score.zone_distance_m)
                    <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_ZONE_MAX_M
                    and retrieval_centered_started_monotonic is not None
                    and (now_monotonic - retrieval_centered_started_monotonic)
                    >= DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S
                    and ball_motion_m is not None
                    and ball_motion_m <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MOTION_MAX_M
                    and unsecured_still_dwell_ready
                    and float(current_capture.ball_x_m) >= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MIN_X_M
                    and float(current_capture.ball_x_m) <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MAX_X_M
                    and abs(float(current_capture.ball_y_m))
                    >= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MIN_LATERAL_M
                    and abs(float(current_capture.ball_y_m))
                    <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_ROLLTHROUGH_MAX_LATERAL_M
                ):
                    return True
                if (
                    not bool(current_zone_score.center_inside_zone)
                    and float(current_zone_score.zone_distance_m)
                    <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_ZONE_MAX_M
                    and retrieval_centered_started_monotonic is not None
                    and (now_monotonic - retrieval_centered_started_monotonic)
                    >= DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S
                    and ball_motion_m is not None
                    and ball_motion_m <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MOTION_MAX_M
                    and unsecured_still_dwell_ready
                    and float(current_capture.ball_x_m) >= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MIN_X_M
                    and float(current_capture.ball_x_m) <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MAX_X_M
                    and abs(float(current_capture.ball_y_m))
                    >= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MIN_LATERAL_M
                    and abs(float(current_capture.ball_y_m))
                    <= DEFAULT_OBJECT_CENTRIC_UNSECURE_RETRIEVAL_HIGH_LATERAL_MAX_LATERAL_M
                ):
                    return True
                if float(current_zone_score.zone_distance_m) > DEFAULT_OBJECT_CENTRIC_UNSECURE_SETTLE_ZONE_MAX_M:
                    return False
                if (
                    bool(current_zone_score.center_inside_zone)
                    and ball_motion_m is not None
                    and ball_motion_m <= DEFAULT_SETTLE_NO_CHASE_MOTION_TOLERANCE_M
                    and unsecured_still_dwell_ready
                ):
                    return True
                if (
                    pre_release_still_started_monotonic is None
                    or (now_monotonic - pre_release_still_started_monotonic) < DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S
                ):
                    return False
                return bool(
                    ball_motion_m is not None
                    and ball_motion_m <= DEFAULT_SETTLE_NO_CHASE_MOTION_TOLERANCE_M
                )
            if (
                object_centric_family
                and current_capture
                and current_capture.ball_ahead
                and not current_capture.captured
                and not current_capture.within_recapture_window
                and not bool(current_zone_score.center_inside_zone)
                and float(current_zone_score.zone_distance_m) > DEFAULT_OBJECT_CENTRIC_UNSECURE_SETTLE_ZONE_MAX_M
            ):
                return False
            if float(current_zone_score.zone_distance_m) > max(float(self.zone.retrieval_radius_m) - 0.05, 0.0):
                return False
            dwell_started = retrieval_centered_started_monotonic
            if dwell_started is None or (now_monotonic - dwell_started) < DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S:
                return False
            if ball_motion_m is None:
                return (
                    pre_release_still_started_monotonic is not None
                    and (now_monotonic - pre_release_still_started_monotonic) >= DEFAULT_SETTLE_NO_CHASE_ENTRY_DWELL_S
                )
            return bool(
                ball_motion_m <= DEFAULT_SETTLE_NO_CHASE_MOTION_TOLERANCE_M
                or _motion_trending_slower()
            )

        def _multi_ball_advance_ready(
            *,
            current_zone_score: Any = None,
            ball_motion_m: float | None = None,
            now_monotonic: float,
        ) -> bool:
            if self.args.scenario_id != "gather_three_ball_zone":
                return False
            if not current_zone_score or not bool(current_zone_score.center_inside_retrieval_corral):
                return False
            if float(current_zone_score.zone_distance_m) > max(float(self.zone.retrieval_radius_m) - 0.05, 0.0):
                return False
            dwell_started = retrieval_centered_started_monotonic
            if dwell_started is None or (now_monotonic - dwell_started) < DEFAULT_MULTI_BALL_ADVANCE_DWELL_S:
                return False
            if ball_motion_m is None:
                return True
            return bool(
                ball_motion_m <= DEFAULT_MULTI_BALL_ADVANCE_MOTION_TOLERANCE_M
                or _motion_trending_slower()
            )

        def _reset_release_monitor(current_ball_pose: dict[str, Any] | None = None) -> None:
            nonlocal release_monitoring_active
            nonlocal release_origin_monotonic
            nonlocal release_samples
            nonlocal release_prev_ball_pose
            nonlocal release_inside_seen
            nonlocal settle_no_chase_active
            nonlocal settle_no_chase_exit_started_monotonic
            nonlocal release_gate_blocked_reason
            release_monitoring_active = False
            release_origin_monotonic = None
            release_samples = []
            release_prev_ball_pose = dict(current_ball_pose or {}) if current_ball_pose else None
            release_inside_seen = False
            settle_no_chase_active = False
            settle_no_chase_exit_started_monotonic = None
            release_gate_blocked_reason = "none"

        def _begin_release_monitor(
            *,
            now_monotonic: float,
            current_capture: Any,
            current_ball_pose: dict[str, Any] | None,
            current_zone_score: Any,
            rationale: str,
            feedback: str,
            settle_no_chase: bool = False,
        ) -> None:
            nonlocal release_monitoring_active
            nonlocal release_origin_monotonic
            nonlocal release_samples
            nonlocal release_prev_ball_pose
            nonlocal release_inside_seen
            nonlocal settle_no_chase_active
            nonlocal settle_no_chase_activated
            nonlocal settle_no_chase_exit_started_monotonic
            nonlocal settle_no_chase_exit_reason
            nonlocal release_gate_blocked_reason
            _record_stop_capture(current_capture)
            _record_release_capture(current_capture)
            release_monitoring_active = True
            release_origin_monotonic = now_monotonic
            settle_no_chase_active = bool(settle_no_chase)
            settle_no_chase_activated = settle_no_chase_activated or settle_no_chase_active
            settle_no_chase_exit_started_monotonic = None
            settle_no_chase_exit_reason = "none"
            release_gate_blocked_reason = "none"
            release_samples = [
                self._release_sample(
                    release_started_monotonic=now_monotonic,
                    now_monotonic=now_monotonic,
                    ball_pose=current_ball_pose,
                    zone_score=current_zone_score,
                )
            ]
            release_prev_ball_pose = dict(current_ball_pose or {}) if current_ball_pose else None
            release_inside_seen = bool(current_zone_score.center_inside_retrieval_corral) if current_zone_score else False
            self._set_manual_drive(False, mode="settle_no_chase" if settle_no_chase_active else "release_settle", rationale=rationale)
            self._update_gather_runtime_state(
                latest_feedback=feedback,
                settle_metrics=_settle_metrics(),
            )

        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            _dashboard_state, robot_pose, ball_pose = self._control_loop_state(session_id=session_id, target=target)
            capture = capture_snapshot(robot_pose, ball_pose or {}, self.capture_envelope) if robot_pose and ball_pose else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
            zone_edge_eligible = zone_edge_correction_eligible(
                capture=capture,
                zone_score=zone_score,
                zone=self.zone,
            )
            local_settle_correction_eligible = _local_settle_correction_eligible(
                current_capture=capture,
                current_zone_score=zone_score,
            )
            if ball_pose:
                self._update_prior_from_ball_pose(target.id, ball_pose)
            if capture and capture.captured:
                last_captured_monotonic = now_monotonic
                if local_recovery_started_monotonic is not None:
                    local_recovery_started_monotonic = None
                    recaptured_settle_started_monotonic = now_monotonic
            if zone_score and zone_score.center_inside_retrieval_corral:
                retrieval_centered_started_monotonic = (
                    now_monotonic
                    if retrieval_centered_started_monotonic is None
                    else retrieval_centered_started_monotonic
                )
            else:
                retrieval_centered_started_monotonic = None
            if zone_score and zone_score.center_inside_zone:
                control_centered_started_monotonic = (
                    now_monotonic
                    if control_centered_started_monotonic is None
                    else control_centered_started_monotonic
                )
            else:
                control_centered_started_monotonic = None
            self._update_gather_runtime_state(
                mission_phase="place",
                gather_phase="place",
                capture_state=capture.to_dict() if capture else {},
                zone_score=zone_score.to_dict() if zone_score else {},
                latest_feedback=f"Placing {target.label} into the zone.",
            )
            self._update_visit_runtime_state(
                proof_state="placing",
                mission_phase="place",
                latest_feedback=f"Placing {target.label} into the zone.",
            )
            ball_motion_m = pose_delta_m(release_prev_ball_pose, ball_pose) if release_prev_ball_pose is not None else None
            if ball_motion_m is not None:
                recent_ball_motion_samples.append(float(ball_motion_m))
                recent_ball_motion_samples[:] = recent_ball_motion_samples[-4:]
            still_motion_threshold = (
                max(DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M * 2.0, 0.02)
                if capture and (capture.captured or capture.within_recapture_window)
                else DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
            )
            if (
                zone_score
                and zone_score.center_inside_retrieval_corral
                and ball_motion_m is not None
                and ball_motion_m <= still_motion_threshold
            ):
                pre_release_still_started_monotonic = (
                    now_monotonic
                    if pre_release_still_started_monotonic is None
                    else pre_release_still_started_monotonic
                )
            else:
                pre_release_still_started_monotonic = None
            append_jsonl(
                state_history_path,
                {
                    "generated_utc": utc_now(),
                    "phase": "place",
                    "attempt": int(attempt_index),
                    "attempt_kind": str(attempt_kind),
                    "target_id": target.id,
                    "robot_pose": robot_pose,
                    "ball_pose": ball_pose,
                    "capture": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "local_recovery_active": bool(local_recovery_started_monotonic is not None),
                    "local_recovery_attempted": bool(local_recovery_attempted),
                    "zone_edge_correction_eligible": bool(local_settle_correction_eligible),
                    "zone_edge_correction_count": int(zone_edge_correction_count),
                    "release_monitoring_active": bool(release_monitoring_active),
                    "settle_no_chase_active": bool(settle_no_chase_active),
                    "settle_no_chase_activated": bool(settle_no_chase_activated),
                    "release_gate_blocked_reason": clean_text(release_gate_blocked_reason, "none"),
                    "release_recontact_count": int(release_recontact_count),
                    "ball_motion_m": ball_motion_m,
                    **self._control_debug_fields(),
                },
            )
            if release_monitoring_active and release_origin_monotonic is not None:
                release_sample = self._release_sample(
                    release_started_monotonic=release_origin_monotonic,
                    now_monotonic=now_monotonic,
                    ball_pose=ball_pose,
                    zone_score=zone_score,
                )
                if ball_motion_m is not None:
                    release_sample["ball_motion_m"] = ball_motion_m
                release_samples.append(release_sample)
                release_prev_ball_pose = dict(ball_pose or {})
                if zone_score and zone_score.center_inside_retrieval_corral:
                    release_inside_seen = True
                settle_metrics = _settle_metrics()
                self._set_manual_drive(
                    False,
                    mode="settle_no_chase" if settle_no_chase_active else "release_settle",
                    rationale=(
                        f"Ball is inside the retrieval corral and slowing; stop chasing and let {self.surface_profile} settle it."
                        if settle_no_chase_active
                        else f"Ball entered the release corridor; letting {self.surface_profile} friction settle it."
                    ),
                )
                self._update_gather_runtime_state(
                    latest_feedback=(
                        f"Holding position while {target.label} settles inside the retrieval corral."
                        if settle_no_chase_active
                        else f"Letting {target.label} settle on {self.surface_profile}."
                    ),
                    settle_metrics=settle_metrics,
                )
                if bool(settle_metrics.get("settled_in_corral_pass", False)):
                    if settle_no_chase_active and settle_no_chase_exit_reason == "none":
                        settle_no_chase_exit_reason = (
                            "corrected" if bool(zone_edge_correction_count or release_recontact_count) else "settled"
                        )
                    settle_exit_reason = default_settle_exit_reason(
                        settled_in_corral_pass=True,
                        corrected=bool(zone_edge_correction_count or release_recontact_count),
                    )
                    return True, {
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "final_ball_pose": ball_pose,
                        "settle_metrics": {**settle_metrics, "settle_exit_reason": settle_exit_reason},
                        "release_recontact_count": release_recontact_count,
                        "settle_exit_reason": settle_exit_reason,
                        **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                        **_settle_fields({**settle_metrics, "settle_exit_reason": settle_exit_reason}),
                        **_retention_fields(),
                        **_settle_no_chase_fields(),
                    }
                release_elapsed_s = now_monotonic - release_origin_monotonic
                within_zone_overlap = bool(zone_score and zone_score.inside_retrieval_corral)
                center_inside_now = bool(zone_score and zone_score.center_inside_retrieval_corral)
                outside_no_chase_window = bool(
                    zone_score is None
                    or float(zone_score.retrieval_distance_m) > (float(self.zone.retrieval_radius_m) + DEFAULT_SETTLE_NO_CHASE_ESCAPE_MARGIN_M)
                )
                multi_ball_advance_ready = _multi_ball_advance_ready(
                    current_zone_score=zone_score,
                    ball_motion_m=ball_motion_m,
                    now_monotonic=now_monotonic,
                )
                if (
                    settle_no_chase_active
                    and center_inside_now
                    and not outside_no_chase_window
                    and multi_ball_advance_ready
                ):
                    if settle_no_chase_exit_reason == "none":
                        settle_no_chase_exit_reason = (
                            "corrected" if bool(zone_edge_correction_count or release_recontact_count) else "settled"
                        )
                    settle_exit_reason = default_settle_exit_reason(
                        settled_in_corral_pass=False,
                        corrected=bool(zone_edge_correction_count or release_recontact_count),
                    )
                    return True, {
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "final_ball_pose": ball_pose,
                        "settle_metrics": {**settle_metrics, "settle_exit_reason": settle_exit_reason},
                        "release_recontact_count": release_recontact_count,
                        "settle_exit_reason": settle_exit_reason,
                        **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                        **_settle_fields({**settle_metrics, "settle_exit_reason": settle_exit_reason}),
                        **_retention_fields(),
                        **_settle_no_chase_fields(),
                    }
                if settle_no_chase_active:
                    object_centric_no_chase_overlap_recontact = bool(
                        self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                        and within_zone_overlap
                        and zone_score
                        and not bool(zone_score.center_inside_zone)
                        and release_recontact_count < 1
                        and capture
                        and (
                            not capture.ball_ahead
                            or float(capture.ball_x_m) < 0.0
                            or abs(float(capture.ball_y_m)) > 1.0
                            or (
                                capture.ball_ahead
                                and not capture.captured
                                and not capture.within_recapture_window
                                and ball_motion_m is not None
                                and ball_motion_m > DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
                                and zone_score
                                and float(zone_score.zone_distance_m) > float(self.zone.control_radius_m)
                                and float(zone_score.zone_distance_m) <= float(self.zone.retrieval_radius_m)
                                and float(capture.ball_x_m) >= 1.0
                                and abs(float(capture.ball_y_m)) <= 0.35
                            )
                        )
                    )
                    if object_centric_no_chase_overlap_recontact:
                        release_recontact_count += 1
                        zone_edge_correction_count += 1
                        zone_edge_correction_started_monotonic = now_monotonic
                        settle_no_chase_exit_reason = "corrected"
                        _reset_release_monitor(ball_pose)
                        self._append_runtime_event(
                            f"{target.label}: early correction after leaving the center during object-centric no-chase.",
                            key=f"settle_no_chase_overlap_recontact:{target.id}:{release_recontact_count}",
                        )
                        self._update_gather_runtime_state(
                            latest_feedback=f"Recontacting {target.label} before it leaves the retrieval overlap.",
                            settle_metrics=settle_metrics,
                        )
                        time.sleep(self.args.poll_s)
                        continue
                    if outside_no_chase_window:
                        settle_no_chase_exit_started_monotonic = (
                            now_monotonic
                            if settle_no_chase_exit_started_monotonic is None
                            else settle_no_chase_exit_started_monotonic
                        )
                        escape_elapsed_s = now_monotonic - settle_no_chase_exit_started_monotonic
                        if escape_elapsed_s < DEFAULT_SETTLE_NO_CHASE_ESCAPE_TIMEOUT_S:
                            self._update_gather_runtime_state(
                                latest_feedback=f"Holding position while {target.label} tests the corral edge.",
                                settle_metrics=settle_metrics,
                            )
                            time.sleep(self.args.poll_s)
                            continue
                        if release_recontact_count < 1 and local_settle_correction_eligible:
                            release_recontact_count += 1
                            zone_edge_correction_count += 1
                            zone_edge_correction_started_monotonic = now_monotonic
                            settle_no_chase_exit_reason = "corrected"
                            _reset_release_monitor(ball_pose)
                            self._append_runtime_event(
                                f"{target.label}: one gentle correction after leaving the settle-no-chase envelope.",
                                key=f"settle_no_chase_recontact:{target.id}:{release_recontact_count}",
                            )
                            self._update_gather_runtime_state(
                                latest_feedback=f"Gently correcting {target.label} after it drifted beyond the corral settle window.",
                                settle_metrics=settle_metrics,
                            )
                            time.sleep(self.args.poll_s)
                            continue
                        settle_no_chase_exit_reason = "rolled_out"
                        self._set_manual_drive(False, mode="release_roll_away", rationale="Ball left the corral after settle-no-chase monitoring.")
                        settle_exit_reason = default_settle_exit_reason(
                            failure_reason="release_roll_away",
                            rolled_away_after_release=True,
                        )
                        return False, {
                            "failure_reason": "release_roll_away",
                            "failure_stage": "release",
                            "capture_state": capture.to_dict() if capture else {},
                            "zone_score": zone_score.to_dict() if zone_score else {},
                            "local_recovery_attempted": local_recovery_attempted,
                            "settle_metrics": {**settle_metrics, "settle_exit_reason": settle_exit_reason},
                            "release_recontact_count": release_recontact_count,
                            "settle_exit_reason": settle_exit_reason,
                            **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                            **_settle_fields({**settle_metrics, "settle_exit_reason": settle_exit_reason}),
                            **_retention_fields(),
                            **_settle_no_chase_fields(),
                        }
                    else:
                        settle_no_chase_exit_started_monotonic = None
                if within_zone_overlap and (ball_motion_m is None or ball_motion_m > DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M):
                    self._update_gather_runtime_state(
                        latest_feedback=(
                            f"Holding position while {target.label} settles inside the corral."
                            if settle_no_chase_active
                            else f"Letting {target.label} keep settling inside the corral overlap."
                        ),
                        settle_metrics=settle_metrics,
                    )
                    time.sleep(self.args.poll_s)
                    continue
                if (
                    not bool(settle_metrics.get("final_inside_retrieval_corral", False))
                    and not within_zone_overlap
                    and release_elapsed_s >= DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
                    and capture
                    and capture.within_recapture_window
                    and local_settle_correction_eligible
                    and release_recontact_count < 1
                ):
                    release_recontact_count += 1
                    zone_edge_correction_count += 1
                    zone_edge_correction_started_monotonic = now_monotonic
                    _reset_release_monitor(ball_pose)
                    self._append_runtime_event(
                        f"{target.label}: gentle recontact after short release on {self.surface_profile}.",
                        key=f"release_recontact_short:{target.id}:{release_recontact_count}",
                    )
                    self._update_gather_runtime_state(
                        latest_feedback=f"Recontacting {target.label} after short release.",
                        settle_metrics=settle_metrics,
                    )
                elif bool(settle_metrics.get("rolled_away_after_release", False)):
                    if within_zone_overlap and (ball_motion_m is None or ball_motion_m > DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M):
                        self._update_gather_runtime_state(
                            latest_feedback=f"Watching {target.label} settle near the corral edge.",
                            settle_metrics=settle_metrics,
                        )
                    elif (
                        release_recontact_count < 1
                        and (
                            local_settle_correction_eligible
                            or within_zone_overlap
                        )
                    ):
                        release_recontact_count += 1
                        zone_edge_correction_count += 1
                        zone_edge_correction_started_monotonic = now_monotonic
                        _reset_release_monitor(ball_pose)
                        feedback = (
                            f"Recontacting {target.label} after an edge settle outside the retrieval corral."
                            if within_zone_overlap and not (capture and capture.within_recapture_window)
                            else f"Recontacting {target.label} after release roll-away."
                        )
                        self._append_runtime_event(
                            f"{target.label}: gentle recontact after release drift on {self.surface_profile}.",
                            key=f"release_recontact_overshoot:{target.id}:{release_recontact_count}",
                        )
                        self._update_gather_runtime_state(
                            latest_feedback=feedback,
                            settle_metrics=settle_metrics,
                        )
                    else:
                        self._set_manual_drive(False, mode="release_roll_away", rationale="Ball rolled away from the corral after release.")
                        settle_exit_reason = default_settle_exit_reason(
                            failure_reason="release_roll_away",
                            rolled_away_after_release=True,
                        )
                        return False, {
                            "failure_reason": "release_roll_away",
                            "failure_stage": "release",
                            "capture_state": capture.to_dict() if capture else {},
                            "zone_score": zone_score.to_dict() if zone_score else {},
                            "local_recovery_attempted": local_recovery_attempted,
                            "settle_metrics": {**settle_metrics, "settle_exit_reason": settle_exit_reason},
                            "release_recontact_count": release_recontact_count,
                            "settle_exit_reason": settle_exit_reason,
                            **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                            **_settle_fields({**settle_metrics, "settle_exit_reason": settle_exit_reason}),
                            **_retention_fields(),
                            **_settle_no_chase_fields(),
                        }
                elif release_elapsed_s >= max(DEFAULT_RELEASE_SETTLE_MAX_WAIT_S, DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S + 3.0):
                    if within_zone_overlap and center_inside_now:
                        self._update_gather_runtime_state(
                            latest_feedback=f"Waiting for {target.label} to fully stop inside the corral.",
                            settle_metrics=settle_metrics,
                        )
                    elif (
                        within_zone_overlap
                        and not center_inside_now
                        and release_recontact_count < 1
                        and ball_motion_m is not None
                        and ball_motion_m <= DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
                    ):
                        release_recontact_count += 1
                        zone_edge_correction_count += 1
                        zone_edge_correction_started_monotonic = now_monotonic
                        _reset_release_monitor(ball_pose)
                        self._append_runtime_event(
                            f"{target.label}: gentle recontact after stopping on the corral edge.",
                            key=f"release_recontact_edge:{target.id}:{release_recontact_count}",
                        )
                        self._update_gather_runtime_state(
                            latest_feedback=f"Nudging {target.label} back into the retrieval corral after it stopped on the edge.",
                            settle_metrics=settle_metrics,
                        )
                    elif (
                        release_recontact_count < 1
                        and (
                            (not within_zone_overlap and local_settle_correction_eligible)
                        )
                    ):
                        release_recontact_count += 1
                        zone_edge_correction_count += 1
                        zone_edge_correction_started_monotonic = now_monotonic
                        _reset_release_monitor(ball_pose)
                        self._append_runtime_event(
                            f"{target.label}: gentle recontact after long unsettled release on {self.surface_profile}.",
                            key=f"release_recontact_unsettled:{target.id}:{release_recontact_count}",
                        )
                        self._update_gather_runtime_state(
                            latest_feedback=f"Recontacting {target.label} after a long unsettled release.",
                            settle_metrics=settle_metrics,
                        )
                    else:
                        if settle_no_chase_active and settle_no_chase_exit_reason == "none":
                            settle_no_chase_exit_reason = "timeout"
                        self._set_manual_drive(False, mode="release_unsettled", rationale="Ball did not finish retrieved and stopped in the corral.")
                        settle_exit_reason = default_settle_exit_reason(failure_reason="release_unsettled")
                        return False, {
                            "failure_reason": "release_unsettled",
                            "failure_stage": "release",
                            "capture_state": capture.to_dict() if capture else {},
                            "zone_score": zone_score.to_dict() if zone_score else {},
                            "local_recovery_attempted": local_recovery_attempted,
                            "settle_metrics": {**settle_metrics, "settle_exit_reason": settle_exit_reason},
                            "release_recontact_count": release_recontact_count,
                            "settle_exit_reason": settle_exit_reason,
                            **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                            **_settle_fields({**settle_metrics, "settle_exit_reason": settle_exit_reason}),
                            **_retention_fields(),
                            **_settle_no_chase_fields(),
                        }
                time.sleep(self.args.poll_s)
                continue
            release_prev_ball_pose = dict(ball_pose or {}) if ball_pose else release_prev_ball_pose
            settle_monitor_ready = _settle_monitor_ready(
                current_capture=capture,
                current_zone_score=zone_score,
                ball_motion_m=ball_motion_m,
                now_monotonic=now_monotonic,
            )
            settle_shepherd_needed = bool(
                zone_score
                and zone_score.center_inside_retrieval_corral
                and capture
                and capture.ball_ahead
                and not capture.captured
                and not capture.within_recapture_window
                and not settle_monitor_ready
            )
            settle_no_chase_ready = _settle_no_chase_ready(
                current_capture=capture,
                current_zone_score=zone_score,
                ball_motion_m=ball_motion_m,
                now_monotonic=now_monotonic,
            )
            secure_release_ready = bool(
                capture
                and secure_capture(capture, self.capture_envelope)
                and release_ready(capture=capture, zone_score=zone_score, zone=self.zone)
            )
            if (
                zone_score
                and zone_score.center_inside_retrieval_corral
                and settle_no_chase_ready
            ):
                escaped_zone_correction_started_monotonic = None
                _begin_release_monitor(
                    now_monotonic=now_monotonic,
                    current_capture=capture,
                    current_ball_pose=ball_pose,
                    current_zone_score=zone_score,
                    rationale=f"Ball is inside the practical retrieval corral and slowing; stop chasing and verify settle on {self.surface_profile}.",
                    feedback=f"Holding position while {target.label} settles inside the retrieval corral.",
                    settle_no_chase=True,
                )
                time.sleep(self.args.poll_s)
                continue
            if zone_score and zone_score.center_inside_zone and settle_monitor_ready and secure_release_ready:
                escaped_zone_correction_started_monotonic = None
                _begin_release_monitor(
                    now_monotonic=now_monotonic,
                    current_capture=capture,
                    current_ball_pose=ball_pose,
                    current_zone_score=zone_score,
                    rationale=f"Ball reached the corral center; verifying settle on {self.surface_profile}.",
                    feedback=f"Verifying that {target.label} settles in the corral.",
                )
                time.sleep(self.args.poll_s)
                continue
            if secure_release_ready:
                marginal_capture_started_monotonic = None
                escaped_zone_correction_started_monotonic = None
                _begin_release_monitor(
                    now_monotonic=now_monotonic,
                    current_capture=capture,
                    current_ball_pose=ball_pose,
                    current_zone_score=zone_score,
                    rationale=f"Ball reached the release corridor; letting {self.surface_profile} friction settle it.",
                    feedback=f"Letting {target.label} settle on {self.surface_profile}.",
                )
                time.sleep(self.args.poll_s)
                continue
            release_gate_blocked_reason = "none"
            if zone_score and zone_score.center_inside_retrieval_corral and not settle_no_chase_ready:
                release_gate_blocked_reason = "no_settle_safe_zone"
            elif release_ready(capture=capture, zone_score=zone_score, zone=self.zone) and not secure_release_ready:
                release_gate_blocked_reason = "no_secure_capture"
            local_recovery_viable = bool(capture and capture.within_recapture_window)
            if local_settle_correction_eligible or local_recovery_viable:
                escaped_zone_correction_started_monotonic = None
            else:
                escaped_zone_correction_started_monotonic = (
                    now_monotonic
                    if escaped_zone_correction_started_monotonic is None
                    else escaped_zone_correction_started_monotonic
                )
            stationary_recapture_state = bool(
                local_recovery_started_monotonic is not None
                and capture
                and capture.within_recapture_window
                and zone_score
                and float(zone_score.zone_distance_m) > (float(self.zone.retrieval_radius_m) + 0.40)
                and abs(float(capture.ball_y_m)) <= 0.04
                and ball_motion_m is not None
                and ball_motion_m <= DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
            )
            if stationary_recapture_state:
                current_stationary_signature = (
                    round(float(capture.ball_x_m), 3),
                    round(float(capture.ball_y_m), 3),
                    round(float(zone_score.zone_distance_m), 3),
                )
                if current_stationary_signature != stationary_recapture_signature:
                    stationary_recapture_signature = current_stationary_signature
                    stationary_recapture_started_monotonic = now_monotonic
                elif stationary_recapture_started_monotonic is None:
                    stationary_recapture_started_monotonic = now_monotonic
            else:
                stationary_recapture_signature = None
                stationary_recapture_started_monotonic = None
            stationary_recapture_nudge_ready = bool(
                stationary_recapture_started_monotonic is not None
                and (now_monotonic - stationary_recapture_started_monotonic) >= DEFAULT_STATIONARY_RECAPTURE_NUDGE_DELAY_S
            )
            local_recovery_active = local_recovery_started_monotonic is not None
            object_centric_far_lateral_recenter_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECENTER_MAX_X_M
                and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_FAR_RECENTER_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_RECENTER_MAX_LATERAL_M
            )
            object_centric_far_wide_lateral_recenter_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_WIDE_RECENTER_MAX_X_M
                and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_FAR_WIDE_RECENTER_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_WIDE_RECENTER_MAX_LATERAL_M
            )
            object_centric_far_extreme_opposed_recenter_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.captured
                and zone_score
                and ball_pose
                and ball_motion_m is not None
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_MOTION_M
                and float(zone_score.zone_distance_m)
                >= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MIN_ZONE_MARGIN_M
                )
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_ZONE_MARGIN_M
                )
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_X_M
                and abs(float(capture.ball_y_m))
                > OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MIN_LATERAL_M
                and abs(float(capture.ball_y_m))
                <= OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_LATERAL_M
                and float(capture.ball_y_m) * (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) < 0.0
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_FAR_EXTREME_OPPOSED_RECENTER_MAX_WORLD_LATERAL_M
            )
            object_centric_far_same_side_high_lateral_recenter_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.captured
                and not capture.within_recapture_window
                and zone_score
                and ball_pose
                and ball_motion_m is not None
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_MOTION_M
                and float(zone_score.zone_distance_m)
                >= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MIN_ZONE_MARGIN_M
                )
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_ZONE_MARGIN_M
                )
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_X_M
                and abs(float(capture.ball_y_m))
                >= OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MIN_LATERAL_M
                and abs(float(capture.ball_y_m))
                <= OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_LATERAL_M
                and float(capture.ball_y_m) * (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) > 0.0
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_FAR_SAME_SIDE_HIGH_LATERAL_RECENTER_MAX_WORLD_LATERAL_M
            )
            object_centric_far_transition_opposed_recenter_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.captured
                and not capture.within_recapture_window
                and zone_score
                and ball_pose
                and ball_motion_m is not None
                and ball_motion_m >= OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_MOTION_M
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_MOTION_M
                and float(zone_score.zone_distance_m)
                >= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_ZONE_MARGIN_M
                )
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_ZONE_MARGIN_M
                )
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_X_M
                and abs(float(capture.ball_y_m))
                > OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_LATERAL_M
                and abs(float(capture.ball_y_m))
                <= OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_LATERAL_M
                and float(capture.ball_y_m) * (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) < 0.0
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_FAR_TRANSITION_OPPOSED_RECENTER_MAX_WORLD_LATERAL_M
            )
            object_centric_far_world_moderate_recenter_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and ball_pose
                and ball_motion_m is not None
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_MOTION_M
                and float(zone_score.zone_distance_m)
                >= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MIN_ZONE_MARGIN_M
                )
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_X_M
                and abs(float(capture.ball_y_m))
                <= OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_WORLD_LATERAL_M
            )
            object_centric_far_world_high_lateral_recenter_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and ball_pose
                and ball_motion_m is not None
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_MOTION_M
                and float(zone_score.zone_distance_m)
                >= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MIN_ZONE_MARGIN_M
                )
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_ZONE_MARGIN_M
                )
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_X_M
                and abs(float(capture.ball_y_m))
                <= OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_FAR_WORLD_HIGH_LATERAL_RECENTER_MAX_WORLD_LATERAL_M
            )
            object_centric_far_positive_world_edge_hold_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.captured
                and zone_score
                and ball_pose
                and ball_motion_m is not None
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and (
                    (
                        ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                        and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_MOTION_M
                    )
                    or ball_motion_m <= 0.005
                )
                and (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MIN_WORLD_LATERAL_M
                and (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_WORLD_LATERAL_M
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_X_M
                and (float(capture.ball_x_m) >= 0.85 or float(capture.ball_y_m) >= 0.0)
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_LATERAL_M
                and (
                    (
                        (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) <= 0.60
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        >= 0.75
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        <= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MAX_ZONE_MARGIN_M
                    )
                    or (
                        (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) >= 0.60
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        >= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MIN_ZONE_MARGIN_M
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        <= 0.75
                        and abs(float(capture.ball_y_m)) >= 0.55
                    )
                    or (
                        (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) >= 0.50
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        >= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MIN_ZONE_MARGIN_M
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        <= 0.75
                        and abs(float(capture.ball_y_m)) >= 0.90
                    )
                    or (
                        float(capture.ball_y_m) >= 0.0
                        and (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) >= 0.35
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        >= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MIN_ZONE_MARGIN_M
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        <= 0.78
                        and abs(float(capture.ball_y_m)) >= 0.85
                    )
                    or (
                        ball_motion_m <= 0.005
                        and (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) >= 0.55
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        >= OBJECT_CENTRIC_PLACE_FAR_POSITIVE_WORLD_EDGE_HOLD_MIN_ZONE_MARGIN_M
                        and (
                            float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                        )
                        <= 0.85
                    )
                )
            )
            object_centric_far_keepup_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_KEEPUP_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_KEEPUP_MAX_X_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_KEEPUP_LATERAL_M
            )
            object_centric_far_line_recapture_keepup_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and capture.within_recapture_window
                and zone_score
                and ball_motion_m is not None
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_MOVING_LINE_RECENTER_MAX_MOTION_M
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_RECOVERY_RECENTER_MAX_X_M
                and (
                    (
                        ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                        and
                        abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_FAR_MOVING_LINE_RECENTER_MIN_LATERAL_M
                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_RECOVERY_RECENTER_MAX_LATERAL_M
                    )
                    or (
                        ball_motion_m >= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MIN_MOTION_M
                        and
                        ball_pose
                        and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                        >= OBJECT_CENTRIC_PLACE_FAR_WORLD_RECENTER_KEEPUP_MIN_WORLD_LATERAL_M
                        and float(capture.ball_x_m)
                        <= OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_X_M
                        and abs(float(capture.ball_y_m))
                        <= OBJECT_CENTRIC_PLACE_FAR_WORLD_MODERATE_LINE_RECENTER_MAX_LATERAL_M
                    )
                )
            )
            object_centric_far_line_keepup_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and (
                    (
                        float(zone_score.zone_distance_m)
                        <= (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_NEAR_ZONE_MARGIN_M + 0.05)
                        and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_KEEPUP_MIN_X_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_LINE_RECENTER_KEEPUP_MAX_X_M
                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_LINE_RECENTER_MAX_CAPTURE_LATERAL_M
                    )
                    or (
                        ball_motion_m is not None
                        and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                        and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_MOVING_LINE_RECENTER_MAX_MOTION_M
                        and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_MOVING_LINE_RECENTER_MIN_X_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_LINE_RECENTER_KEEPUP_MAX_X_M
                        and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_FAR_RECENTER_MIN_LATERAL_M
                        and abs(float(capture.ball_y_m))
                        <= OBJECT_CENTRIC_PLACE_FAR_MOVING_LINE_RECENTER_MAX_LATERAL_M
                    )
                )
            )
            object_centric_far_straight_rollout_coast_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.captured
                and not capture.within_recapture_window
                and zone_score
                and ball_pose
                and ball_motion_m is not None
                and ball_motion_m >= OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MIN_MOTION_M
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_MOTION_M
                and (
                    float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                )
                >= OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MIN_ZONE_MARGIN_M
                and (
                    float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                )
                <= OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_ZONE_MARGIN_M
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_X_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_FAR_STRAIGHT_ROLLOUT_COAST_MAX_WORLD_LATERAL_M
            )
            object_centric_far_captured_gap_keepup_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and (capture.captured or capture.within_recapture_window)
                and zone_score
                and ball_pose
                and ball_motion_m is not None
                and ball_motion_m >= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_MOTION_M
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_MOTION_M
                and (
                    float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                )
                >= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_ZONE_MARGIN_M
                and (
                    float(zone_score.zone_distance_m) - float(self.zone.retrieval_radius_m)
                )
                <= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_ZONE_MARGIN_M
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_X_M
                and abs(float(capture.ball_y_m)) >= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_LATERAL_M
                and float(capture.ball_y_m) * (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) < 0.0
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_WORLD_LATERAL_M
                and (
                    (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y)) < 0.0
                    or (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                    <= OBJECT_CENTRIC_PLACE_FAR_CAPTURED_GAP_KEEPUP_MAX_POSITIVE_WORLD_LATERAL_M
                )
            )
            object_centric_far_recapture_reel_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and (
                    float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_X_M
                    or (
                        ball_motion_m is not None
                        and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_HIGH_X_MAX_X_M
                        and float(zone_score.zone_distance_m)
                        <= (
                            float(self.zone.retrieval_radius_m)
                            + OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_KEEPUP_MARGIN_M
                        )
                    )
                )
                and (
                    (
                        float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MIN_X_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_X_M
                        and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MIN_LATERAL_M
                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_LATERAL_M
                    )
                    or (
                        float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MIN_X_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_X_M
                        and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MIN_LATERAL_M
                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MAX_LATERAL_M
                    )
                    or (
                        float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_X_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_HIGH_X_MAX_X_M
                        and abs(float(capture.ball_y_m))
                        > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_HIGH_X_MIN_LATERAL_M
                        and abs(float(capture.ball_y_m))
                        <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_KEEPUP_MAX_LATERAL_M
                        and ball_motion_m is not None
                        and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                        and float(zone_score.zone_distance_m)
                        <= (
                            float(self.zone.retrieval_radius_m)
                            + OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_KEEPUP_MARGIN_M
                        )
                    )
                )
            )
            object_centric_far_low_x_recapture_reel_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and ball_motion_m is not None
                and ball_motion_m >= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MIN_MOTION_M
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and float(zone_score.zone_distance_m)
                <= (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MAX_ZONE_MARGIN_M)
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MAX_X_M
                and abs(float(capture.ball_y_m)) >= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LOW_X_MAX_LATERAL_M
            )
            object_centric_far_high_x_line_recenter_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and ball_pose
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MAX_X_M
                and abs(float(capture.ball_y_m))
                <= OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MAX_CAPTURE_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MIN_LATERAL_TO_ZONE_M
            )
            object_centric_far_reorient_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and not capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and ball_pose
                and ball_motion_m is not None
                and ball_motion_m <= DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MAX_MOTION_M
                and float(zone_score.zone_distance_m)
                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                and float(capture.ball_x_m) >= DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MIN_X_M
                and float(capture.ball_x_m) <= DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MAX_X_M
                and abs(float(capture.ball_y_m)) <= DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MAX_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= DEFAULT_OBJECT_CENTRIC_FAR_REORIENT_MAX_WORLD_LATERAL_M
            )
            object_centric_near_lateral_recenter_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and not zone_score.inside_retrieval_corral
                and float(zone_score.zone_distance_m) > float(self.zone.retrieval_radius_m)
                and float(zone_score.zone_distance_m)
                <= (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MARGIN_M)
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_X_M
                and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_LATERAL_M
            )
            object_centric_near_finish_keepup_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and not zone_score.inside_retrieval_corral
                and float(zone_score.zone_distance_m) > float(self.zone.retrieval_radius_m)
                and float(zone_score.zone_distance_m)
                <= (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_NEAR_FINISH_KEEPUP_MARGIN_M)
                and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_FINISH_KEEPUP_MAX_X_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_FINISH_KEEPUP_LATERAL_M
            )
            object_centric_near_forward_keepup_available = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and not zone_score.inside_retrieval_corral
                and float(zone_score.zone_distance_m) > float(self.zone.retrieval_radius_m)
                and float(zone_score.zone_distance_m)
                <= (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_NEAR_ZONE_MARGIN_M)
                and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_FORWARD_KEEPUP_MAX_X_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_FORWARD_KEEPUP_LATERAL_M
            )
            object_centric_near_wide_reel_common = bool(
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and capture
                and capture.ball_ahead
                and not capture.within_recapture_window
                and zone_score
                and not zone_score.inside_retrieval_corral
                and float(zone_score.zone_distance_m) > float(self.zone.retrieval_radius_m)
                and float(zone_score.zone_distance_m)
                <= (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_NEAR_ZONE_MARGIN_M)
            )
            object_centric_near_low_x_opposed_wide_reel_available = bool(
                object_centric_near_wide_reel_common
                and ball_motion_m is not None
                and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MAX_MOTION_M
                and ball_pose
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MAX_X_M
                and abs(float(capture.ball_y_m)) >= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MAX_LATERAL_M
                and (float(capture.ball_y_m) * (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))) < 0.0
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MAX_WORLD_LATERAL_M
                and float(zone_score.zone_distance_m)
                >= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_NEAR_LOW_X_OPPOSED_WIDE_REEL_MIN_ZONE_MARGIN_M
                )
            )
            object_centric_near_low_x_same_side_edge_hold_available = bool(
                object_centric_near_wide_reel_common
                and ball_motion_m is not None
                and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_MOTION_M
                and ball_pose
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_X_M
                and abs(float(capture.ball_y_m)) >= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_LATERAL_M
                and (float(capture.ball_y_m) * (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))) > 0.0
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_WORLD_LATERAL_M
                and float(zone_score.zone_distance_m)
                >= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MIN_ZONE_MARGIN_M
                )
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_NEAR_LOW_X_SAME_SIDE_EDGE_HOLD_MAX_ZONE_MARGIN_M
                )
            )
            object_centric_near_stale_edge_wide_hold_available = bool(
                object_centric_near_wide_reel_common
                and ball_motion_m is not None
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_MOTION_M
                and ball_pose
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_ZONE_MARGIN_M
                )
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_X_M
                and abs(float(capture.ball_y_m)) >= OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_NEAR_EDGE_STALE_WIDE_HOLD_MAX_WORLD_LATERAL_M
            )
            object_centric_near_high_x_final_edge_hold_available = bool(
                object_centric_near_wide_reel_common
                and ball_motion_m is not None
                and (
                    (
                        ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                        and ball_motion_m <= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_MOTION_M
                        and (
                            abs(float(capture.ball_y_m)) <= 0.18
                            or (
                                float(capture.ball_y_m)
                                * (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                            )
                            < 0.0
                        )
                    )
                    or ball_motion_m <= 0.005
                )
                and ball_pose
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_ZONE_MARGIN_M
                )
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_X_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_FINAL_EDGE_HOLD_MAX_WORLD_LATERAL_M
            )
            object_centric_near_high_x_escape_edge_hold_available = bool(
                object_centric_near_wide_reel_common
                and ball_motion_m is not None
                and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                and ball_motion_m <= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_MOTION_M
                and ball_pose
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_X_M
                and abs(float(capture.ball_y_m)) >= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_LATERAL_M
                and (float(capture.ball_y_m) * (float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))) < 0.0
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_WORLD_LATERAL_M
                and float(zone_score.zone_distance_m)
                >= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MIN_ZONE_MARGIN_M
                )
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_NEAR_HIGH_X_ESCAPE_EDGE_HOLD_MAX_ZONE_MARGIN_M
                )
            )
            object_centric_near_mouth_world_edge_resteer_available = bool(
                object_centric_near_wide_reel_common
                and ball_motion_m is not None
                and (ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M or ball_motion_m <= 0.005)
                and ball_pose
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MAX_ZONE_MARGIN_M
                )
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MAX_X_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MAX_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_NEAR_MOUTH_WORLD_EDGE_RESTEER_MAX_WORLD_LATERAL_M
            )
            object_centric_near_edge_escape_world_hold_available = bool(
                object_centric_near_wide_reel_common
                and ball_motion_m is not None
                and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                and ball_pose
                and float(zone_score.zone_distance_m)
                <= (
                    float(self.zone.retrieval_radius_m)
                    + OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MAX_ZONE_MARGIN_M
                )
                and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MIN_X_M
                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MAX_X_M
                and abs(float(capture.ball_y_m)) >= OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MIN_LATERAL_M
                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MAX_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                >= OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MIN_WORLD_LATERAL_M
                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                <= OBJECT_CENTRIC_PLACE_NEAR_EDGE_ESCAPE_WORLD_HOLD_MAX_WORLD_LATERAL_M
            )
            object_centric_near_wide_reel_available = bool(
                object_centric_near_wide_reel_common
                and (
                    object_centric_near_low_x_opposed_wide_reel_available
                    or object_centric_near_low_x_same_side_edge_hold_available
                    or object_centric_near_stale_edge_wide_hold_available
                    or object_centric_near_high_x_final_edge_hold_available
                    or object_centric_near_high_x_escape_edge_hold_available
                    or object_centric_near_mouth_world_edge_resteer_available
                    or object_centric_near_edge_escape_world_hold_available
                    or
                    (
                        float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MIN_X_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MAX_X_M
                        and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MIN_LATERAL_M
                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MAX_LATERAL_M
                    )
                    or (
                        ball_motion_m is not None
                        and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_X_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MIN_X_M
                        and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MIN_LATERAL_M
                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_LATERAL_M
                    )
                    or (
                        ball_motion_m is not None
                        and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                        and ball_pose
                        and float(zone_score.zone_distance_m)
                        > (
                            float(self.zone.retrieval_radius_m)
                            + OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MIN_ZONE_MARGIN_M
                        )
                        and float(capture.ball_x_m) >= OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MIN_X_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MAX_X_M
                        and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MIN_LATERAL_M
                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MAX_LATERAL_M
                        and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                        <= OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_LOW_X_MAX_WORLD_LATERAL_M
                    )
                    or (
                        ball_motion_m is not None
                        and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                        and float(zone_score.zone_distance_m)
                        <= (
                            float(self.zone.retrieval_radius_m)
                            + OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_EDGE_MARGIN_M
                        )
                        and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MAX_X_M
                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_EDGE_MAX_X_M
                        and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MIN_LATERAL_M
                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_WIDE_REEL_MAX_LATERAL_M
                    )
                )
            )
            if local_recovery_active:
                if (
                    recaptured_settle_started_monotonic is None
                    and (not local_recovery_viable)
                    and (not local_settle_correction_eligible)
                    and (not object_centric_far_lateral_recenter_available)
                    and (not object_centric_far_wide_lateral_recenter_available)
                    and (not object_centric_far_extreme_opposed_recenter_available)
                    and (not object_centric_far_same_side_high_lateral_recenter_available)
                    and (not object_centric_far_transition_opposed_recenter_available)
                    and (not object_centric_far_world_moderate_recenter_available)
                    and (not object_centric_far_world_high_lateral_recenter_available)
                    and (not object_centric_far_positive_world_edge_hold_available)
                    and (not object_centric_far_keepup_available)
                    and (not object_centric_far_line_keepup_available)
                    and (not object_centric_far_straight_rollout_coast_available)
                    and (not object_centric_far_recapture_reel_available)
                    and (not object_centric_far_low_x_recapture_reel_available)
                    and (not object_centric_far_high_x_line_recenter_available)
                    and (not object_centric_far_reorient_available)
                    and (not object_centric_near_lateral_recenter_available)
                    and (not object_centric_near_finish_keepup_available)
                    and (not object_centric_near_forward_keepup_available)
                    and (not object_centric_near_wide_reel_available)
                ):
                    escape_elapsed_s = (
                        now_monotonic - escaped_zone_correction_started_monotonic
                        if escaped_zone_correction_started_monotonic is not None
                        else 0.0
                    )
                    if escape_elapsed_s < DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S:
                        self._set_manual_drive(False, mode="zone_edge_wait", rationale="Waiting briefly to confirm the ball truly left local correction range.")
                        self._update_gather_runtime_state(
                            latest_feedback=f"Watching {target.label} before escalating outside local correction.",
                        )
                        time.sleep(self.args.poll_s)
                        continue
                    self._set_manual_drive(False, mode="release_roll_away", rationale="Ball left the corral correction window during place.")
                    if settle_no_chase_active and settle_no_chase_exit_reason == "none":
                        settle_no_chase_exit_reason = "rolled_out"
                    return False, {
                        "failure_reason": "release_roll_away",
                        "failure_stage": "release",
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "local_recovery_attempted": local_recovery_attempted,
                        "rolled_away_after_release": True,
                        "settle_exit_reason": "rolled_out",
                        **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                        **_settle_fields({"rolled_away_after_release": True, "settle_exit_reason": "rolled_out"}),
                        **_retention_fields(),
                        **_settle_no_chase_fields(),
                    }
            elif capture and not capture.captured:
                marginal_capture_started_monotonic = None
                if local_recovery_viable or local_settle_correction_eligible:
                    if not local_recovery_attempted:
                        local_recovery_attempted = True
                        self._append_runtime_event(
                            f"{target.label}: short local recapture during place.",
                            key=f"place_local_recovery:{target.id}",
                        )
                    local_recovery_started_monotonic = now_monotonic
                    recaptured_settle_started_monotonic = None
                    if local_settle_correction_eligible and zone_edge_correction_started_monotonic is None:
                        zone_edge_correction_started_monotonic = now_monotonic
                        zone_edge_correction_count += 1
                    feedback = (
                        f"Gently correcting {target.label} near the corral edge."
                        if local_settle_correction_eligible
                        else f"Recovering {target.label} after brief capture loss."
                    )
                    self._update_gather_runtime_state(latest_feedback=feedback)
                else:
                    escape_elapsed_s = (
                        now_monotonic - escaped_zone_correction_started_monotonic
                        if escaped_zone_correction_started_monotonic is not None
                        else 0.0
                    )
                    if escape_elapsed_s < DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S:
                        self._set_manual_drive(False, mode="zone_edge_wait", rationale="Waiting briefly before leaving place control.")
                        self._update_gather_runtime_state(
                            latest_feedback=f"Watching {target.label} before escalating outside local correction.",
                        )
                        time.sleep(self.args.poll_s)
                        continue
                    self._set_manual_drive(False, mode="release_roll_away", rationale="Ball left the corral correction window during place.")
                    if settle_no_chase_active and settle_no_chase_exit_reason == "none":
                        settle_no_chase_exit_reason = "rolled_out"
                    return False, {
                        "failure_reason": "release_roll_away",
                        "failure_stage": "release",
                        "capture_state": capture.to_dict(),
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "local_recovery_attempted": local_recovery_attempted,
                        "rolled_away_after_release": True,
                        "settle_exit_reason": "rolled_out",
                        **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                        **_settle_fields({"rolled_away_after_release": True, "settle_exit_reason": "rolled_out"}),
                        **_retention_fields(),
                        **_settle_no_chase_fields(),
                    }
            elif capture_loss_detected(
                captured_now=False,
                last_captured_monotonic=last_captured_monotonic,
                now_monotonic=now_monotonic,
                loss_grace_s=self.capture_envelope.loss_grace_s,
            ):
                marginal_capture_started_monotonic = None
                escape_elapsed_s = (
                    now_monotonic - escaped_zone_correction_started_monotonic
                    if escaped_zone_correction_started_monotonic is not None
                    else DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S
                )
                if local_settle_correction_eligible or escape_elapsed_s < DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S:
                    self._set_manual_drive(False, mode="zone_edge_wait", rationale="Holding briefly while the ball pose recovers near the corral.")
                    self._update_gather_runtime_state(
                        latest_feedback=f"Holding for {target.label} to settle back into view near the corral.",
                    )
                    time.sleep(self.args.poll_s)
                    continue
                self._set_manual_drive(False, mode="release_roll_away", rationale="Ball left the corral correction window during place.")
                if settle_no_chase_active and settle_no_chase_exit_reason == "none":
                    settle_no_chase_exit_reason = "rolled_out"
                return False, {
                    "failure_reason": "release_roll_away",
                    "failure_stage": "release",
                    "capture_state": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "local_recovery_attempted": local_recovery_attempted,
                    "rolled_away_after_release": True,
                    "settle_exit_reason": "rolled_out",
                    **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                    **_settle_fields({"rolled_away_after_release": True, "settle_exit_reason": "rolled_out"}),
                    **_retention_fields(),
                    **_settle_no_chase_fields(),
                }
            if recaptured_settle_started_monotonic is not None:
                settle_elapsed_s = now_monotonic - recaptured_settle_started_monotonic
                if settle_elapsed_s < DEFAULT_PLACE_RECOVERY_SETTLE_S:
                    self._set_manual_drive(False, mode="capture_settle", rationale="Ball recaptured; settling before place.")
                    self._update_gather_runtime_state(latest_feedback=f"Stabilizing {target.label} after recapture.")
                    time.sleep(self.args.poll_s)
                    continue
                recaptured_settle_started_monotonic = None
            if capture and capture.captured:
                marginal_capture_now = (
                    (abs(float(capture.ball_y_m)) > 0.04 or float(capture.ball_x_m) < 0.08)
                    and not object_centric_far_captured_gap_keepup_available
                )
                if marginal_capture_now:
                    marginal_capture_started_monotonic = marginal_capture_started_monotonic or now_monotonic
                else:
                    marginal_capture_started_monotonic = None
                if marginal_capture_now and (now_monotonic - marginal_capture_started_monotonic) < DEFAULT_PLACE_MARGINAL_CAPTURE_SETTLE_S:
                    command = compute_place_command(robot_pose, ball_pose or {}, zone=self.zone, envelope=self.capture_envelope) if robot_pose and ball_pose else None
                    if command is not None:
                        self._set_manual_drive(
                            True,
                            linear_x=command.linear_x,
                            angular_z=command.angular_z,
                            mode=command.mode,
                            rationale=command.rationale,
                        )
                        self._update_gather_runtime_state(
                            latest_control_command=command.to_dict(),
                            latest_feedback=f"Settling {target.label} inside the spur before the final push.",
                        )
                    time.sleep(self.args.poll_s)
                    continue
            else:
                marginal_capture_started_monotonic = None
            command = compute_place_command(robot_pose, ball_pose or {}, zone=self.zone, envelope=self.capture_envelope) if robot_pose and ball_pose else None
            if (
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and robot_pose
                and ball_pose
            ):
                object_decision = decide_object_centric_gather_command(
                    robot_pose,
                    ball_pose or {},
                    phase="place",
                    zone=self.zone,
                    envelope=self.capture_envelope,
                    previous_command=object_centric_place_previous_command,
                    previous_ball_pose=object_centric_place_previous_ball_pose,
                )
                if object_decision.command is not None:
                    command = object_decision.command
            if command is not None:
                object_centric_inside_retrieval_hold = bool(
                    self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                    and command.mode in {"object_place_inside_retrieval_hold", "object_place_inside_retrieval_shepherd"}
                    and zone_score
                    and (zone_score.center_inside_retrieval_corral or zone_score.inside_retrieval_corral)
                )
                if object_centric_inside_retrieval_hold:
                    local_recovery_started_monotonic = None
                    recaptured_settle_started_monotonic = None
                    if command.mode == "object_place_inside_retrieval_shepherd":
                        self._set_manual_drive(
                            True,
                            linear_x=command.linear_x,
                            angular_z=command.angular_z,
                            mode=command.mode,
                            rationale=command.rationale,
                        )
                    else:
                        self._set_manual_drive(
                            False,
                            mode=command.mode,
                            rationale=command.rationale,
                        )
                    self._update_gather_runtime_state(
                        latest_feedback=f"Holding position while {target.label} settles inside the retrieval corral.",
                        latest_control_command=command.to_dict(),
                    )
                    object_centric_place_previous_command = command
                    object_centric_place_previous_ball_pose = (
                        dict(ball_pose or {}) if ball_pose else object_centric_place_previous_ball_pose
                    )
                    time.sleep(self.args.poll_s)
                    continue
                if (
                    local_settle_correction_eligible
                    and zone_score
                    and zone_score.inside_retrieval_corral
                    and ball_motion_m is not None
                    and ball_motion_m > DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
                    and not settle_shepherd_needed
                ):
                    if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                        object_centric_place_previous_ball_pose = (
                            dict(ball_pose or {}) if ball_pose else object_centric_place_previous_ball_pose
                        )
                    self._set_manual_drive(False, mode="zone_edge_wait", rationale="Ball is still moving inside the corral overlap; let it settle before nudging again.")
                    self._update_gather_runtime_state(
                        latest_feedback=f"Letting {target.label} settle near the corral edge before another correction.",
                        latest_control_command={
                            "mode": "zone_edge_wait",
                            "linear_x": 0.0,
                            "angular_z": 0.0,
                            "target_speed_scale": 0.0,
                            "rationale": "Ball is still moving inside the corral overlap; let it settle before nudging again.",
                        },
                    )
                    time.sleep(self.args.poll_s)
                    continue
                if local_recovery_started_monotonic is not None:
                    object_centric_lateral_place_recenter = bool(
                        self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                        and command.mode
                        in {
                            "object_place_lateral_recenter",
                            "object_place_far_line_recenter",
                            "object_place_far_wide_lateral_recenter",
                        }
                        and not (
                            command.mode == "object_place_far_line_recenter"
                            and float(command.linear_x) > 0.0
                            and (
                                object_centric_far_line_keepup_available
                                or object_centric_far_line_recapture_keepup_available
                            )
                        )
                        and capture
                        and capture.ball_ahead
                        and zone_score
                        and (
                            object_centric_far_world_moderate_recenter_available
                            or
                                object_centric_far_world_high_lateral_recenter_available
                                or
                                object_centric_far_positive_world_edge_hold_available
                                or
                                object_centric_far_same_side_high_lateral_recenter_available
                                or
                                object_centric_far_transition_opposed_recenter_available
                                or
                                object_centric_far_straight_rollout_coast_available
                                or
                                (
                                capture.within_recapture_window
                                and float(zone_score.zone_distance_m) > (float(self.zone.retrieval_radius_m) + 0.40)
                            )
                            or (
                                (not capture.within_recapture_window)
                                and float(zone_score.zone_distance_m)
                                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECENTER_MAX_X_M
                                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_RECENTER_MAX_LATERAL_M
                            )
                            or (
                                (not capture.within_recapture_window)
                                and float(zone_score.zone_distance_m)
                                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_WIDE_RECENTER_MAX_X_M
                                and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_FAR_WIDE_RECENTER_MIN_LATERAL_M
                                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_WIDE_RECENTER_MAX_LATERAL_M
                            )
                            or (
                                (not capture.within_recapture_window)
                                and ball_pose
                                and float(zone_score.zone_distance_m)
                                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                                and float(capture.ball_x_m)
                                > OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MIN_X_M
                                and float(capture.ball_x_m)
                                <= OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MAX_X_M
                                and abs(float(capture.ball_y_m))
                                <= OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MAX_CAPTURE_LATERAL_M
                                and abs(float(ball_pose.get("y", 0.0)) - float(self.zone.world_y))
                                >= OBJECT_CENTRIC_PLACE_FAR_HIGH_X_LINE_RECENTER_MIN_LATERAL_TO_ZONE_M
                            )
                            or (
                                (not capture.within_recapture_window)
                                and not zone_score.inside_retrieval_corral
                                and float(zone_score.zone_distance_m) > float(self.zone.retrieval_radius_m)
                                and float(zone_score.zone_distance_m)
                                <= (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MARGIN_M)
                                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_X_M
                                and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MIN_LATERAL_M
                                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_LATERAL_M
                            )
                        )
                    )
                    object_centric_place_drive_preserve = False
                    if (
                        self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                        and command.mode
                        in {
                            "object_place_drive_to_zone",
                            "object_place_recapture_drive",
                            "object_place_far_line_recenter",
                            "object_place_far_recapture_reel",
                            "object_place_near_zone_recapture_drive",
                            "object_place_near_zone_wide_reel",
                        }
                        and capture
                        and capture.ball_ahead
                        and zone_score
                    ):
                        if capture.within_recapture_window:
                            preserve_margin_m = (
                                0.0 if command.mode == "object_place_near_zone_recapture_drive" else 0.40
                            )
                            object_centric_place_drive_preserve = bool(
                                float(zone_score.zone_distance_m)
                                > (float(self.zone.retrieval_radius_m) + preserve_margin_m)
                            )
                        elif command.mode == "object_place_recapture_drive":
                            object_centric_place_drive_preserve = bool(
                                float(zone_score.zone_distance_m)
                                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                                and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_KEEPUP_MIN_X_M
                                and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_KEEPUP_MAX_X_M
                                and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_KEEPUP_LATERAL_M
                            )
                        elif command.mode == "object_place_far_line_recenter":
                            object_centric_place_drive_preserve = bool(
                                (
                                    object_centric_far_line_keepup_available
                                    or object_centric_far_line_recapture_keepup_available
                                )
                                and float(command.linear_x) > 0.0
                            )
                        elif command.mode == "object_place_far_recapture_reel":
                            object_centric_place_drive_preserve = bool(
                                float(zone_score.zone_distance_m)
                                > (float(self.zone.retrieval_radius_m) + OBJECT_CENTRIC_PLACE_FAR_ZONE_MARGIN_M)
                                and (
                                    float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_X_M
                                    or (
                                        ball_motion_m is not None
                                        and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                                        and float(capture.ball_x_m)
                                        <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_HIGH_X_MAX_X_M
                                        and float(zone_score.zone_distance_m)
                                        <= (
                                            float(self.zone.retrieval_radius_m)
                                            + OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_KEEPUP_MARGIN_M
                                        )
                                    )
                                )
                                and (
                                    (
                                        float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MIN_X_M
                                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_X_M
                                        and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MIN_LATERAL_M
                                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_LATERAL_M
                                    )
                                    or (
                                        float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MIN_X_M
                                        and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_X_M
                                        and abs(float(capture.ball_y_m)) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MIN_LATERAL_M
                                        and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_WIDE_MAX_LATERAL_M
                                    )
                                    or (
                                        float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_MAX_X_M
                                        and float(capture.ball_x_m)
                                        <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_HIGH_X_MAX_X_M
                                        and abs(float(capture.ball_y_m))
                                        > OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_HIGH_X_MIN_LATERAL_M
                                        and abs(float(capture.ball_y_m))
                                        <= OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_KEEPUP_MAX_LATERAL_M
                                        and ball_motion_m is not None
                                        and ball_motion_m > OBJECT_CENTRIC_PLACE_COAST_MOTION_GUARD_M
                                        and float(zone_score.zone_distance_m)
                                        <= (
                                            float(self.zone.retrieval_radius_m)
                                            + OBJECT_CENTRIC_PLACE_FAR_RECAPTURE_REEL_LATE_KEEPUP_MARGIN_M
                                        )
                                    )
                                )
                            )
                        elif command.mode == "object_place_near_zone_recapture_drive":
                            object_centric_place_drive_preserve = bool(
                                (
                                    float(zone_score.zone_distance_m) > float(self.zone.retrieval_radius_m)
                                    and float(zone_score.zone_distance_m)
                                    <= (
                                        float(self.zone.retrieval_radius_m)
                                        + OBJECT_CENTRIC_PLACE_NEAR_FINISH_KEEPUP_MARGIN_M
                                    )
                                    and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_X_M
                                    and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_FINISH_KEEPUP_MAX_X_M
                                    and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_FINISH_KEEPUP_LATERAL_M
                                )
                                or (
                                    not zone_score.inside_retrieval_corral
                                    and float(zone_score.zone_distance_m) > float(self.zone.retrieval_radius_m)
                                    and float(zone_score.zone_distance_m)
                                    <= (
                                        float(self.zone.retrieval_radius_m)
                                        + OBJECT_CENTRIC_PLACE_NEAR_ZONE_MARGIN_M
                                    )
                                    and float(capture.ball_x_m) > OBJECT_CENTRIC_PLACE_NEAR_RECENTER_MAX_X_M
                                    and float(capture.ball_x_m) <= OBJECT_CENTRIC_PLACE_NEAR_FORWARD_KEEPUP_MAX_X_M
                                    and abs(float(capture.ball_y_m)) <= OBJECT_CENTRIC_PLACE_NEAR_FORWARD_KEEPUP_LATERAL_M
                                )
                            )
                        elif command.mode == "object_place_near_zone_wide_reel":
                            object_centric_place_drive_preserve = bool(
                                object_centric_near_wide_reel_available
                            )
                    if object_centric_lateral_place_recenter:
                        lateral_recenter_angular_limit = (
                            0.80
                            if (
                                command.mode == "object_place_far_wide_lateral_recenter"
                                or object_centric_far_world_high_lateral_recenter_available
                                or object_centric_far_positive_world_edge_hold_available
                            )
                            else 0.45
                        )
                        command = command.__class__(
                            mode=(
                                "object_place_far_wide_lateral_recenter"
                                if command.mode == "object_place_far_wide_lateral_recenter"
                                else "object_place_lateral_recenter"
                            ),
                            linear_x=0.0,
                            angular_z=round(
                                clamp(
                                    float(command.angular_z),
                                    -lateral_recenter_angular_limit,
                                    lateral_recenter_angular_limit,
                                ),
                                6,
                            ),
                            target_speed_scale=0.0,
                            rationale="Preserve the object-centric lateral recenter before resuming far-zone recapture push.",
                        )
                    elif object_centric_place_drive_preserve:
                        command_linear = float(command.linear_x)
                        recovery_linear = 0.0 if command_linear <= 0.0 else min(max(command_linear, 0.025), 0.085)
                        if (
                            command.mode
                            in {
                                "object_place_far_line_recenter",
                                "object_place_far_recapture_reel",
                                "object_place_near_zone_wide_reel",
                            }
                            and command_linear > 0.0
                        ):
                            recovery_linear = min(max(command_linear, 0.010), 0.032)
                        if command.mode == "object_place_near_zone_recapture_drive" and command_linear > 0.0:
                            recovery_linear = min(max(command_linear, 0.012), 0.040)
                        if capture and abs(float(capture.ball_y_m)) > 0.12:
                            capture_ball_x = float(capture.ball_x_m)
                            capture_lateral_abs = abs(float(capture.ball_y_m))
                            keepup_recapture = bool(
                                command_linear >= 0.060
                                and capture_ball_x >= 0.65
                                and capture_lateral_abs <= 0.16
                            )
                            if keepup_recapture:
                                recovery_linear = max(recovery_linear, min(command_linear, 0.085))
                            else:
                                recovery_linear = min(recovery_linear, 0.030)
                        command = command.__class__(
                            mode=command.mode,
                            linear_x=round(recovery_linear, 6),
                            angular_z=round(
                                clamp(
                                    float(command.angular_z),
                                    -0.80
                                    if command.mode
                                    in {"object_place_far_recapture_reel", "object_place_near_zone_wide_reel"}
                                    else -0.45,
                                    0.80
                                    if command.mode
                                    in {"object_place_far_recapture_reel", "object_place_near_zone_wide_reel"}
                                    else 0.45,
                                ),
                                6,
                            ),
                            target_speed_scale=min(float(command.target_speed_scale), 0.65),
                            rationale="Continue the object-centric far-zone recapture push instead of holding while the ball rolls away.",
                        )
                    else:
                        recovery_linear = min(float(command.linear_x), 0.05)
                        recovery_angular = clamp(float(command.angular_z), -0.45, 0.45)
                        recovery_scale = min(float(command.target_speed_scale), 0.55)
                        recovery_mode = "capture_recovery"
                        recovery_rationale = "Briefly recenter the ball under the catcher before resuming place."
                        if capture and not capture.ball_ahead:
                            recovery_linear = 0.0
                            recovery_angular = clamp(0.90 if float(capture.ball_y_m) >= 0.0 else -0.90, -0.90, 0.90)
                            recovery_scale = 0.0
                            recovery_mode = "capture_recovery_turn"
                            recovery_rationale = "Ball slipped behind inside the corral; turn in place quickly before it escapes."
                        elif capture and capture.within_recapture_window and (
                            float(capture.ball_x_m) > 0.40 or abs(float(capture.ball_y_m)) > 0.08
                        ):
                            near_zone_hold = bool(
                                zone_score
                                and float(zone_score.zone_distance_m) <= (float(self.zone.retrieval_radius_m) + 0.40)
                            )
                            laterally_misaligned_hold = abs(float(capture.ball_y_m)) > 0.08
                            if laterally_misaligned_hold or near_zone_hold or not stationary_recapture_nudge_ready:
                                recovery_linear = 0.0
                                recovery_angular = clamp((float(capture.ball_y_m) * 5.0), -0.35, 0.35)
                                recovery_scale = 0.30
                                recovery_mode = "capture_recovery_hold"
                                recovery_rationale = "Ball is ahead of the spur mouth; hold and yaw gently before pushing again."
                            else:
                                recovery_rationale = (
                                    "Ball stayed centered in local recovery while still far from the corral; allow a bounded forward recapture nudge."
                                )
                        command = command.__class__(
                            mode=recovery_mode,
                            linear_x=recovery_linear,
                            angular_z=recovery_angular,
                            target_speed_scale=recovery_scale,
                            rationale=recovery_rationale,
                        )
                elif settle_shepherd_needed and command.mode in {"retrieval_hold", "capture", "place_recapture", "place"}:
                    shepherd_linear = 0.02
                    if float(capture.ball_x_m) > 0.95:
                        shepherd_linear = 0.03
                    elif float(capture.ball_x_m) > 0.75:
                        shepherd_linear = 0.025
                    if abs(float(capture.ball_y_m)) > 0.12:
                        shepherd_linear = 0.0
                    command = command.__class__(
                        mode="retrieval_shepherd" if shepherd_linear > 0.0 else "retrieval_hold",
                        linear_x=round(shepherd_linear, 6),
                        angular_z=clamp(float(command.angular_z), -0.30, 0.30),
                        target_speed_scale=0.40 if shepherd_linear > 0.0 else 0.0,
                        rationale="Ball is inside the retrieval corral but still rolling away from the robot; keep a gentle shepherd until settle is credible.",
                    )
                elif local_settle_correction_eligible and command.mode in {"place_recapture", "capture", "place"}:
                    zone_edge_correction_started_monotonic = (
                        now_monotonic
                        if zone_edge_correction_started_monotonic is None
                        else zone_edge_correction_started_monotonic
                    )
                    zone_edge_correction_count = max(zone_edge_correction_count, 1)
                    command = command.__class__(
                        mode="zone_edge_correction",
                        linear_x=min(float(command.linear_x), 0.016),
                        angular_z=clamp(float(command.angular_z), -0.35, 0.35),
                        target_speed_scale=min(float(command.target_speed_scale), 0.45),
                        rationale="Ball is near the corral edge; use one gentle correction instead of escalating to revisit.",
                    )
                self._set_manual_drive(
                    True,
                    linear_x=command.linear_x,
                    angular_z=command.angular_z,
                    mode=command.mode,
                    rationale=command.rationale,
                )
                self._update_gather_runtime_state(latest_control_command=command.to_dict())
                if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                    object_centric_place_previous_command = command
            if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
                object_centric_place_previous_ball_pose = dict(ball_pose or {}) if ball_pose else object_centric_place_previous_ball_pose
            time.sleep(self.args.poll_s)

        self._set_manual_drive(False, mode="place_timeout", rationale="Place timed out.")
        return False, {
            "failure_reason": "place_timeout",
            "failure_stage": "place",
            "local_recovery_attempted": local_recovery_attempted,
            "settle_metrics": _settle_metrics(),
            "release_recontact_count": release_recontact_count,
            "settle_exit_reason": "timeout",
            **_place_diagnostics(allow_full_revisit=False),
            **_settle_fields({"settle_exit_reason": "timeout"}),
            **_retention_fields(),
            **_settle_no_chase_fields(),
        }

    def _fetch_to_pose_target(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
        state_history_path: Path,
        attempt_index: int = 0,
        attempt_kind: str = "",
    ) -> tuple[bool, dict[str, Any]]:
        timeout_budget_s = max(self.args.place_timeout_s, 0.1)
        if self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY:
            timeout_budget_s = max(timeout_budget_s, DEFAULT_OBJECT_CENTRIC_PLACE_TIMEOUT_S)
        fetch_started_monotonic = time.monotonic()
        deadline = fetch_started_monotonic + timeout_budget_s
        fetch_pose_world = self._fetch_pose_world()
        fetch_xyyaw = world_pose_xyyaw(fetch_pose_world)
        previous_command: PlaceControlCommand | None = None
        previous_ball_pose: dict[str, Any] | None = None
        fetch_start_ball_pose: dict[str, Any] | None = None
        latest_ball_pose: dict[str, Any] = {}
        latest_capture: dict[str, Any] = {}
        latest_zone_score: dict[str, Any] = {}
        latest_policy: dict[str, Any] = {}
        nav2_corridor_push_attempted = False
        nav2_corridor_push_diagnostics: dict[str, Any] = {}
        closest_distance_m: float | None = None
        closest_pose: dict[str, Any] = {}
        still_started_monotonic: float | None = None
        latest_still_s: float | None = None
        latest_ball_displacement_m: float | None = None
        ball_moved_since_fetch = False
        max_commanded_linear_x_mps: float | None = None
        max_target_speed_scale: float | None = None
        observe_count = 0
        failure_reason = "fetch_to_pose_timeout"

        def _distance_to_fetch_pose(ball_pose: dict[str, Any] | None) -> float | None:
            if fetch_xyyaw is None or not ball_pose:
                return None
            ball_xyyaw = world_pose_xyyaw(ball_pose)
            if ball_xyyaw is None:
                return None
            return math.hypot(float(ball_xyyaw[0]) - float(fetch_xyyaw[0]), float(ball_xyyaw[1]) - float(fetch_xyyaw[1]))

        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            fetch_elapsed_s = max(0.0, now_monotonic - fetch_started_monotonic)
            _dashboard_state, robot_pose, ball_pose = self._control_loop_state(session_id=session_id, target=target)
            capture = capture_snapshot(robot_pose, ball_pose or {}, self.capture_envelope) if robot_pose and ball_pose else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
            ball_motion_m = pose_delta_m(previous_ball_pose, ball_pose) if previous_ball_pose is not None and ball_pose else None
            if fetch_start_ball_pose is None and ball_pose:
                fetch_start_ball_pose = dict(ball_pose)
            latest_ball_displacement_m = (
                pose_delta_m(fetch_start_ball_pose, ball_pose)
                if fetch_start_ball_pose is not None and ball_pose
                else None
            )
            if (
                (ball_motion_m is not None and ball_motion_m > DEFAULT_FETCH_TO_POSE_LAUNCH_MOTION_EVIDENCE_M)
                or (
                    latest_ball_displacement_m is not None
                    and latest_ball_displacement_m > DEFAULT_FETCH_TO_POSE_LAUNCH_MOTION_EVIDENCE_M
                )
            ):
                ball_moved_since_fetch = True
            distance_to_fetch_pose_m = _distance_to_fetch_pose(ball_pose)
            if ball_pose:
                latest_ball_pose = dict(ball_pose)
                self._update_prior_from_ball_pose(target.id, ball_pose)
            latest_capture = capture.to_dict() if capture else {}
            latest_zone_score = zone_score.to_dict() if zone_score else {}
            observe_count += 1
            if distance_to_fetch_pose_m is not None:
                if closest_distance_m is None or distance_to_fetch_pose_m < closest_distance_m:
                    closest_distance_m = float(distance_to_fetch_pose_m)
                    closest_pose = dict(ball_pose or {})
                if distance_to_fetch_pose_m <= float(self.fetch_delivery_radius_m):
                    self._set_manual_drive(
                        False,
                        mode="fetch_to_pose_complete",
                        rationale="Ball trajectory intersected the delivery radius.",
                    )
                    self._update_gather_runtime_state(
                        mission_phase="advance",
                        gather_phase="advance",
                        latest_feedback=f"{target.label} fetched through the delivery pose.",
                    )
                    return True, {
                        "final_ball_pose": latest_ball_pose,
                        "failure_reason": "",
                        "failure_stage": "",
                        "fetch_observe_count": int(observe_count),
                        "fetch_elapsed_s": round(float(fetch_elapsed_s), 6),
                        "fetch_still_s": (
                            round(float(latest_still_s), 6)
                            if latest_still_s is not None
                            else None
                        ),
                        "fetch_ball_displacement_m": (
                            round(float(latest_ball_displacement_m), 6)
                            if latest_ball_displacement_m is not None
                            else None
                        ),
                        "fetch_ball_moved_since_fetch": bool(ball_moved_since_fetch),
                        "fetch_min_launch_observe_s": round(float(DEFAULT_FETCH_TO_POSE_MIN_LAUNCH_OBSERVE_S), 6),
                        "fetch_launch_motion_evidence_m": round(float(DEFAULT_FETCH_TO_POSE_LAUNCH_MOTION_EVIDENCE_M), 6),
                        "fetch_max_commanded_linear_x_mps": (
                            round(float(max_commanded_linear_x_mps), 6)
                            if max_commanded_linear_x_mps is not None
                            else None
                        ),
                        "fetch_max_target_speed_scale": (
                            round(float(max_target_speed_scale), 6)
                            if max_target_speed_scale is not None
                            else None
                        ),
                        "fetch_closest_approach_distance_m": round(float(closest_distance_m), 6),
                        "fetch_closest_pose": closest_pose,
                        "nav2_follow_path_corridor_push": nav2_corridor_push_diagnostics,
                        "settle_exit_reason": "trajectory_intersects_delivery_radius",
                        "rolled_away_after_release": False,
                    }
            if ball_motion_m is not None and ball_motion_m <= DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M:
                still_started_monotonic = now_monotonic if still_started_monotonic is None else still_started_monotonic
            else:
                still_started_monotonic = None
            latest_still_s = (
                max(0.0, now_monotonic - still_started_monotonic)
                if still_started_monotonic is not None
                else None
            )
            if (
                still_started_monotonic is not None
                and latest_still_s is not None
                and latest_still_s >= DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
                and (
                    ball_moved_since_fetch
                    or fetch_elapsed_s >= DEFAULT_FETCH_TO_POSE_MIN_LAUNCH_OBSERVE_S
                )
                and distance_to_fetch_pose_m is not None
                and distance_to_fetch_pose_m > float(self.fetch_delivery_radius_m)
            ):
                if not failure_reason.startswith("nav2_corridor_push_"):
                    failure_reason = "fetch_to_pose_ball_stopped_short"
                break

            if (
                self.gather_control_family == NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTROL_FAMILY
                and robot_pose
                and ball_pose
                and not nav2_corridor_push_attempted
            ):
                nav2_corridor_push_attempted = True
                corridor_plan = build_nav2_follow_path_corridor_push_plan(
                    robot_pose,
                    ball_pose,
                    fetch_pose_world,
                )
                corridor_plan_dict = corridor_plan.to_dict()
                path_poses = [
                    dict(item)
                    for item in corridor_plan_dict.get("path_poses", [])
                    if isinstance(item, dict)
                ]
                nav2_corridor_push_diagnostics = {
                    "plan": corridor_plan_dict,
                    "dispatch_status": "not_dispatched",
                    "monitor_cancel_live": False,
                    "monitor_cancel_live_reason": "initial_spike_slice_uses_action_timeout_cancel_only",
                }
                append_jsonl(
                    state_history_path,
                    {
                        "generated_utc": utc_now(),
                        "event_type": "nav2_follow_path_corridor_push_plan",
                        "phase": "fetch_to_pose",
                        "attempt": int(attempt_index),
                        "attempt_kind": str(attempt_kind),
                        "target_id": target.id,
                        "robot_pose": robot_pose,
                        "ball_pose": ball_pose,
                        "fetch_pose_world": fetch_pose_world,
                        "nav2_follow_path_plan": corridor_plan_dict,
                        "controller_family": self.gather_control_family,
                    },
                )
                if not bool(corridor_plan_dict.get("active", False)):
                    failure_reason = clean_text(corridor_plan_dict.get("reason"), "nav2_corridor_push_path_unavailable")
                    break
                remaining_timeout_s = max(0.1, deadline - time.monotonic())
                follow_path_timeout_s = min(
                    float(DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_GOAL_TIMEOUT_S),
                    remaining_timeout_s,
                )
                self._set_manual_drive(
                    False,
                    mode="nav2_follow_path_corridor_push",
                    rationale="Nav2 FollowPath owns the corridor-push contact path.",
                )
                self._update_gather_runtime_state(
                    mission_phase="fetch_to_pose",
                    gather_phase="fetch_to_pose",
                    latest_feedback=f"Nav2 corridor-push is fetching {target.label}.",
                )
                try:
                    follow_path_result = self._dispatch_nav2_follow_path_reacquire(
                        compose_project=session_id,
                        path_poses=path_poses,
                        controller_id=clean_text(
                            corridor_plan_dict.get("controller_id"),
                            DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_ID,
                        ),
                        goal_checker_id=clean_text(
                            corridor_plan_dict.get("goal_checker_id"),
                            DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID,
                        ),
                        timeout_s=follow_path_timeout_s,
                    )
                except Exception as exc:
                    follow_path_result = {
                        "dispatch_status": "client_exception",
                        "accepted": False,
                        "success": False,
                        "error": str(exc),
                    }
                nav2_corridor_push_diagnostics = {
                    **nav2_corridor_push_diagnostics,
                    "dispatch_status": clean_text(follow_path_result.get("dispatch_status"), "unknown"),
                    "success": bool(follow_path_result.get("success", False)),
                    "status_code": clean_number(follow_path_result.get("status_code")),
                    "status_text": clean_text(follow_path_result.get("status_text")),
                    "error": clean_text(follow_path_result.get("error")),
                    "timeout_s": clean_rounded_number(follow_path_result.get("timeout_s")),
                    "elapsed_s": clean_rounded_number(follow_path_result.get("elapsed_s")),
                    "timed_out": bool(follow_path_result.get("timed_out", False)),
                    "cancel_requested": bool(follow_path_result.get("cancel_requested", False)),
                    "cmd_vel_counts": follow_path_result.get("cmd_vel_counts", {}),
                    "cmd_vel_last": follow_path_result.get("cmd_vel_last", {}),
                    "odom_delta": follow_path_result.get("odom_delta", {}),
                    "path_progress_last": follow_path_result.get("path_progress_last", {}),
                    "result": follow_path_result,
                }
                append_jsonl(
                    state_history_path,
                    {
                        "generated_utc": utc_now(),
                        "event_type": "nav2_follow_path_corridor_push_result",
                        "phase": "fetch_to_pose",
                        "attempt": int(attempt_index),
                        "attempt_kind": str(attempt_kind),
                        "target_id": target.id,
                        "nav2_follow_path_plan": corridor_plan_dict,
                        "nav2_follow_path_result": follow_path_result,
                        "nav2_follow_path_corridor_push": nav2_corridor_push_diagnostics,
                        "controller_family": self.gather_control_family,
                        "control": self._control_debug_fields(
                            strategy_name=NAV2_FOLLOW_PATH_CORRIDOR_PUSH_OBJECTIVE,
                            objective_name="follow_path_corridor_push",
                        ),
                    },
                )
                if not bool(follow_path_result.get("success", False)):
                    failure_reason = (
                        "nav2_corridor_push_timeout"
                        if bool(follow_path_result.get("timed_out", False))
                        else "nav2_corridor_push_failed"
                    )
                previous_ball_pose = dict(ball_pose or {}) if ball_pose else previous_ball_pose
                time.sleep(self.args.poll_s)
                continue

            command: PlaceControlCommand | None = None
            raw_command: PlaceControlCommand | None = None
            policy_fields: dict[str, Any] = {}
            if (
                self.gather_control_family == OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
                and robot_pose
                and ball_pose
            ):
                decision = decide_object_centric_gather_command(
                    robot_pose,
                    ball_pose,
                    phase="fetch_to_pose",
                    zone=self.zone,
                    envelope=self.capture_envelope,
                    previous_command=previous_command,
                    previous_ball_pose=previous_ball_pose,
                )
                command = decision.command
                raw_command = decision.raw_command
                latest_policy = dict(decision.diagnostics)
                policy_fields = {
                    "object_centric_policy": latest_policy,
                    **self._control_debug_fields(
                        strategy_name=str(decision.strategy_name or ""),
                        objective_name=str(decision.objective_name or ""),
                        progress_score=clean_number(decision.progress_score),
                    ),
                }
            elif self.gather_control_family == NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTROL_FAMILY:
                policy_fields = {
                    "nav2_follow_path_corridor_push": nav2_corridor_push_diagnostics,
                    **self._control_debug_fields(
                        strategy_name=NAV2_FOLLOW_PATH_CORRIDOR_PUSH_OBJECTIVE,
                        objective_name="follow_path_corridor_push_observe",
                    ),
                }
            elif robot_pose and ball_pose:
                command = compute_place_command(robot_pose, ball_pose, zone=self.zone, envelope=self.capture_envelope)
                raw_command = command
                policy_fields = self._control_debug_fields(objective_name="fetch_to_pose_fallback")

            append_jsonl(
                state_history_path,
                {
                    "generated_utc": utc_now(),
                    "event_type": "fetch_to_pose_tick",
                    "phase": "fetch_to_pose",
                    "attempt": int(attempt_index),
                    "attempt_kind": str(attempt_kind),
                    "target_id": target.id,
                    "robot_pose": robot_pose,
                    "ball_pose": ball_pose,
                    "capture": latest_capture,
                    "zone_score": latest_zone_score,
                    "fetch_pose_world": fetch_pose_world,
                    "fetch_to_pose": {
                        "reached": bool(
                            distance_to_fetch_pose_m is not None
                            and distance_to_fetch_pose_m <= float(self.fetch_delivery_radius_m)
                        ),
                        "elapsed_s": round(float(fetch_elapsed_s), 6),
                        "observe_count": int(observe_count),
                        "distance_to_fetch_pose_m": (
                            round(float(distance_to_fetch_pose_m), 6)
                            if distance_to_fetch_pose_m is not None
                            else None
                        ),
                        "closest_approach_distance_m": (
                            round(float(closest_distance_m), 6)
                            if closest_distance_m is not None
                            else None
                        ),
                        "delivery_radius_m": round(float(self.fetch_delivery_radius_m), 6),
                        "still_s": (
                            round(float(latest_still_s), 6)
                            if latest_still_s is not None
                            else None
                        ),
                        "ball_displacement_m": (
                            round(float(latest_ball_displacement_m), 6)
                            if latest_ball_displacement_m is not None
                            else None
                        ),
                        "ball_moved_since_fetch": bool(ball_moved_since_fetch),
                        "min_launch_observe_s": round(float(DEFAULT_FETCH_TO_POSE_MIN_LAUNCH_OBSERVE_S), 6),
                        "launch_motion_evidence_m": round(float(DEFAULT_FETCH_TO_POSE_LAUNCH_MOTION_EVIDENCE_M), 6),
                        "max_commanded_linear_x_mps": (
                            round(float(max_commanded_linear_x_mps), 6)
                            if max_commanded_linear_x_mps is not None
                            else None
                        ),
                        "max_target_speed_scale": (
                            round(float(max_target_speed_scale), 6)
                            if max_target_speed_scale is not None
                            else None
                        ),
                    },
                    "ball_motion_m": ball_motion_m,
                    "selected_command": command.to_dict() if command else {},
                    "raw_command": raw_command.to_dict() if raw_command else {},
                    **policy_fields,
                },
            )
            self._update_gather_runtime_state(
                mission_phase="fetch_to_pose",
                gather_phase="fetch_to_pose",
                capture_state=latest_capture,
                zone_score=latest_zone_score,
                latest_feedback=f"Fetching {target.label} through the delivery pose.",
                last_fetch_to_pose_result={
                    "distance_to_fetch_pose_m": (
                        round(float(distance_to_fetch_pose_m), 6)
                        if distance_to_fetch_pose_m is not None
                        else None
                    ),
                    "closest_approach_distance_m": (
                        round(float(closest_distance_m), 6)
                        if closest_distance_m is not None
                        else None
                    ),
                    "fetch_pose_world": fetch_pose_world,
                },
            )
            self._update_visit_runtime_state(
                proof_state="fetching",
                mission_phase="fetch_to_pose",
                latest_feedback=f"Fetching {target.label} through the delivery pose.",
            )
            if command is not None:
                linear_abs = abs(float(command.linear_x))
                max_commanded_linear_x_mps = (
                    linear_abs
                    if max_commanded_linear_x_mps is None
                    else max(max_commanded_linear_x_mps, linear_abs)
                )
                target_speed_scale = float(command.target_speed_scale)
                max_target_speed_scale = (
                    target_speed_scale
                    if max_target_speed_scale is None
                    else max(max_target_speed_scale, target_speed_scale)
                )
                self._set_manual_drive(
                    True,
                    linear_x=command.linear_x,
                    angular_z=command.angular_z,
                    mode=command.mode,
                    rationale=command.rationale,
                )
                self._update_gather_runtime_state(latest_control_command=command.to_dict())
                previous_command = command
            previous_ball_pose = dict(ball_pose or {}) if ball_pose else previous_ball_pose
            time.sleep(self.args.poll_s)

        self._set_manual_drive(False, mode=failure_reason, rationale="Fetch-to-pose observation budget ended.")
        return False, {
            "failure_reason": failure_reason,
            "failure_stage": "fetch_to_pose",
            "final_ball_pose": latest_ball_pose,
            "capture_state": latest_capture,
            "zone_score": latest_zone_score,
            "object_centric_policy": latest_policy,
            "fetch_observe_count": int(observe_count),
            "fetch_elapsed_s": (
                round(float(max(0.0, time.monotonic() - fetch_started_monotonic)), 6)
            ),
            "fetch_still_s": (
                round(float(latest_still_s), 6)
                if latest_still_s is not None
                else None
            ),
            "fetch_ball_displacement_m": (
                round(float(latest_ball_displacement_m), 6)
                if latest_ball_displacement_m is not None
                else None
            ),
            "fetch_ball_moved_since_fetch": bool(ball_moved_since_fetch),
            "fetch_min_launch_observe_s": round(float(DEFAULT_FETCH_TO_POSE_MIN_LAUNCH_OBSERVE_S), 6),
            "fetch_launch_motion_evidence_m": round(float(DEFAULT_FETCH_TO_POSE_LAUNCH_MOTION_EVIDENCE_M), 6),
            "fetch_max_commanded_linear_x_mps": (
                round(float(max_commanded_linear_x_mps), 6)
                if max_commanded_linear_x_mps is not None
                else None
            ),
            "fetch_max_target_speed_scale": (
                round(float(max_target_speed_scale), 6)
                if max_target_speed_scale is not None
                else None
            ),
            "fetch_closest_approach_distance_m": (
                round(float(closest_distance_m), 6)
                if closest_distance_m is not None
                else None
            ),
            "fetch_closest_pose": closest_pose,
            "nav2_follow_path_corridor_push": nav2_corridor_push_diagnostics,
            "settle_exit_reason": failure_reason,
            "rolled_away_after_release": False,
            "allow_full_revisit": False,
            "local_recovery_attempted": False,
        }

    def _run_target(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
        route_index: int,
        gather_sequence_path: Path,
        state_history_path: Path,
        mission_root: Path,
    ) -> dict[str, Any]:
        attempt = 0
        capture_loss_count = 0
        place_loss_recapture_count = 0
        place_loss_full_revisit_count = 0
        place_controller_reentry_count = 0
        post_visit_revisit_count = 0
        zone_edge_correction_count = 0
        local_recovery_attempted_any = False
        visit_completed_once = False
        active_handoff_kind = ""
        resume_with_capture = False
        resume_with_place_controller = False
        resume_with_place_loss_revisit = False
        resume_with_fresh_approach = False
        target_start_monotonic = time.monotonic()
        latest_approach_progress_memory: dict[str, Any] = {}
        latest_approach_progress_rank: tuple[int, ...] | None = None
        latest_approach_progress_sequence = 0
        active_attempt_approach_index: int | None = None
        active_attempt_approach_memory: dict[str, Any] = {}
        fresh_attempt_index: int | None = None
        fresh_attempt_approach_memory: dict[str, Any] = {}
        fresh_attempt_kinds = {"initial_visit", "retry_visit", "place_loss_revisit"}

        def _retention_kwargs(payload: dict[str, Any] | None) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return {}
            return {
                "stopped_with_ball_captured": bool(payload.get("stopped_with_ball_captured", False)),
                "release_started_with_capture": bool(payload.get("release_started_with_capture", False)),
                "stop_capture_state": payload.get("stop_capture_state", {}) if isinstance(payload.get("stop_capture_state"), dict) else {},
                "release_capture_state": payload.get("release_capture_state", {}) if isinstance(payload.get("release_capture_state"), dict) else {},
                "clean_retention_pass": (
                    bool(payload["clean_retention_pass"])
                    if "clean_retention_pass" in payload
                    else None
                ),
            }

        def _control_diag_kwargs(payload: dict[str, Any] | None) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return {}
            return {
                "settle_no_chase_activated": bool(payload.get("settle_no_chase_activated", False)),
                "settle_no_chase_exit_reason": clean_text(payload.get("settle_no_chase_exit_reason"), "none"),
                "release_gate_blocked_reason": clean_text(payload.get("release_gate_blocked_reason"), "none"),
            }

        def _approach_fields_from_memory(memory: dict[str, Any] | None) -> dict[str, Any]:
            memory = memory if isinstance(memory, dict) else {}
            return {
                "pre_stage_pose_world": (
                    dict(memory["pre_stage_pose_world"])
                    if isinstance(memory.get("pre_stage_pose_world"), dict)
                    else {}
                ),
                "pre_stage_pose_reached": bool(memory.get("pre_stage_pose_reached", False)),
                "pre_stage_time_s": float(clean_number(memory.get("pre_stage_time_s")) or 0.0),
                "pre_stage_handoff_pass": bool(memory.get("pre_stage_handoff_pass", False)),
                "approach_side_verdict": (
                    dict(memory["approach_side_verdict"])
                    if isinstance(memory.get("approach_side_verdict"), dict)
                    else {}
                ),
                "staging_pose_reached": bool(memory.get("staging_pose_reached", False)),
                "entered_goal_side_before_capture": bool(memory.get("entered_goal_side_before_capture", False)),
                "first_contact_push_alignment_deg": clean_number(memory.get("first_contact_push_alignment_deg")),
                "push_direction_yaw_deg": float(clean_number(memory.get("push_direction_yaw_deg")) or 0.0),
                "stage_time_s": float(clean_number(memory.get("stage_time_s")) or 0.0),
                "capture_entry_reached": bool(memory.get("capture_entry_reached", False)),
                "capture_entry_time_s": float(clean_number(memory.get("capture_entry_time_s")) or 0.0),
                "approach_failure_reason": clean_text(memory.get("approach_failure_reason")),
            }

        def _update_approach_memory(memory: dict[str, Any], payload: dict[str, Any] | None) -> None:
            if not isinstance(payload, dict):
                return
            current = {
                "pre_stage_pose_world": payload.get("pre_stage_pose_world", {})
                if isinstance(payload.get("pre_stage_pose_world"), dict)
                else {},
                "pre_stage_pose_reached": bool(payload.get("pre_stage_pose_reached", False)),
                "pre_stage_time_s": float(clean_number(payload.get("pre_stage_time_s")) or 0.0),
                "pre_stage_handoff_pass": bool(payload.get("pre_stage_handoff_pass", False)),
                "approach_side_verdict": payload.get("approach_side_verdict", {})
                if isinstance(payload.get("approach_side_verdict"), dict)
                else {},
                "staging_pose_reached": bool(payload.get("staging_pose_reached", False)),
                "entered_goal_side_before_capture": bool(payload.get("entered_goal_side_before_capture", False)),
                "first_contact_push_alignment_deg": clean_number(payload.get("first_contact_push_alignment_deg")),
                "push_direction_yaw_deg": float(clean_number(payload.get("push_direction_yaw_deg")) or 0.0),
                "stage_time_s": float(clean_number(payload.get("stage_time_s")) or 0.0),
                "capture_entry_reached": bool(payload.get("capture_entry_reached", False)),
                "capture_entry_time_s": float(clean_number(payload.get("capture_entry_time_s")) or 0.0),
                "approach_failure_reason": clean_text(payload.get("approach_failure_reason")),
            }
            if current["pre_stage_pose_world"]:
                memory["pre_stage_pose_world"] = dict(current["pre_stage_pose_world"])
            if current["pre_stage_pose_reached"]:
                memory["pre_stage_pose_reached"] = True
            if current["pre_stage_time_s"] > 0.0:
                memory["pre_stage_time_s"] = current["pre_stage_time_s"]
            if current["pre_stage_handoff_pass"]:
                memory["pre_stage_handoff_pass"] = True
            if current["approach_side_verdict"]:
                memory["approach_side_verdict"] = dict(current["approach_side_verdict"])
            if current["staging_pose_reached"]:
                memory["staging_pose_reached"] = True
            if current["entered_goal_side_before_capture"]:
                memory["entered_goal_side_before_capture"] = True
            if current["first_contact_push_alignment_deg"] is not None:
                memory["first_contact_push_alignment_deg"] = current["first_contact_push_alignment_deg"]
            if current["push_direction_yaw_deg"] or "push_direction_yaw_deg" in payload:
                memory["push_direction_yaw_deg"] = current["push_direction_yaw_deg"]
            if current["stage_time_s"] > 0.0:
                memory["stage_time_s"] = current["stage_time_s"]
            if current["capture_entry_reached"]:
                memory["capture_entry_reached"] = True
            if current["capture_entry_time_s"] > 0.0:
                memory["capture_entry_time_s"] = current["capture_entry_time_s"]
            if current["approach_failure_reason"]:
                memory["approach_failure_reason"] = current["approach_failure_reason"]

        def _approach_progress_rank(
            fields: dict[str, Any],
            *,
            attempt_index: int,
            sequence: int,
        ) -> tuple[int, ...]:
            return (
                1 if fields.get("capture_entry_reached", False) else 0,
                1 if fields.get("staging_pose_reached", False) else 0,
                1 if fields.get("pre_stage_handoff_pass", False) else 0,
                1 if fields.get("pre_stage_pose_reached", False) else 0,
                1 if isinstance(fields.get("pre_stage_pose_world"), dict) and fields.get("pre_stage_pose_world") else 0,
                1 if float(clean_number(fields.get("capture_entry_time_s")) or 0.0) > 0.0 else 0,
                1 if float(clean_number(fields.get("stage_time_s")) or 0.0) > 0.0 else 0,
                1 if float(clean_number(fields.get("pre_stage_time_s")) or 0.0) > 0.0 else 0,
                int(attempt_index),
                int(sequence),
            )

        def _record_latest_approach_progress(payload: dict[str, Any] | None) -> None:
            nonlocal active_attempt_approach_index
            nonlocal active_attempt_approach_memory
            nonlocal latest_approach_progress_memory
            nonlocal latest_approach_progress_rank
            nonlocal latest_approach_progress_sequence
            if not isinstance(payload, dict) or attempt_kind not in fresh_attempt_kinds:
                return
            if active_attempt_approach_index != int(attempt):
                active_attempt_approach_index = int(attempt)
                active_attempt_approach_memory = {}
            _update_approach_memory(active_attempt_approach_memory, payload)
            candidate = _approach_fields_from_memory(active_attempt_approach_memory)
            latest_approach_progress_sequence += 1
            candidate_rank = _approach_progress_rank(
                candidate,
                attempt_index=int(attempt),
                sequence=latest_approach_progress_sequence,
            )
            if latest_approach_progress_rank is None or candidate_rank >= latest_approach_progress_rank:
                latest_approach_progress_rank = candidate_rank
                latest_approach_progress_memory = _approach_fields_from_memory(candidate)

        def _approach_kwargs(payload: dict[str, Any] | None = None) -> dict[str, Any]:
            if isinstance(payload, dict):
                _record_latest_approach_progress(payload)
            return _approach_fields_from_memory(latest_approach_progress_memory)

        def _approach_progress_snapshot_kwargs(memory: dict[str, Any], *, field_name: str) -> dict[str, Any]:
            if not isinstance(memory, dict) or not memory:
                return {field_name: {}}
            fields = _approach_fields_from_memory(memory)
            verdict = fields["approach_side_verdict"]
            entered_goal_side = bool(fields["entered_goal_side_before_capture"])
            pre_stage_pose_reached = bool(fields["pre_stage_pose_reached"])
            staging_pose_reached = bool(fields["staging_pose_reached"])
            capture_entry_reached = bool(fields["capture_entry_reached"])
            if verdict:
                reason = clean_text(verdict.get("reason"))
                progress_pass = bool(verdict.get("pass", False))
                if not reason and not progress_pass:
                    reason = clean_text(fields["approach_failure_reason"])
            elif entered_goal_side:
                reason = "entered_goal_side_before_capture"
                progress_pass = False
            elif not pre_stage_pose_reached:
                reason = clean_text(fields["approach_failure_reason"], "pre_stage_pose_not_reached")
                progress_pass = False
            elif not staging_pose_reached:
                reason = clean_text(fields["approach_failure_reason"], "staging_pose_not_reached")
                progress_pass = False
            elif not capture_entry_reached:
                reason = clean_text(fields["approach_failure_reason"], "capture_entry_not_reached")
                progress_pass = False
            else:
                reason = ""
                progress_pass = True
            return {
                field_name: {
                    "pass": progress_pass,
                    "reason": reason,
                    "pre_stage": {
                        "pose_world": dict(fields["pre_stage_pose_world"]),
                        "pose_reached": pre_stage_pose_reached,
                        "time_s": float(fields["pre_stage_time_s"]),
                        "handoff_pass": bool(fields["pre_stage_handoff_pass"]),
                    },
                    "stage": {
                        "pose_reached": staging_pose_reached,
                        "time_s": float(fields["stage_time_s"]),
                    },
                    "capture_entry": {
                        "pass": progress_pass and capture_entry_reached,
                        "reached": capture_entry_reached,
                        "entered_goal_side_before_capture": entered_goal_side,
                        "first_contact_push_alignment_deg": clean_number(fields["first_contact_push_alignment_deg"]),
                        "push_direction_yaw_deg": float(fields["push_direction_yaw_deg"]),
                        "time_s": float(fields["capture_entry_time_s"]),
                        "failure_reason": "" if reason == "" else clean_text(fields["approach_failure_reason"], reason),
                    },
                }
            }

        def _latest_approach_progress_kwargs() -> dict[str, Any]:
            return _approach_progress_snapshot_kwargs(
                latest_approach_progress_memory,
                field_name="latest_approach_progress",
            )

        def _record_fresh_attempt_approach(
            payload: dict[str, Any] | None,
            *,
            attempt_index: int,
            attempt_kind: str,
        ) -> None:
            nonlocal fresh_attempt_index
            if not isinstance(payload, dict) or attempt_kind not in fresh_attempt_kinds:
                return
            if fresh_attempt_index is None:
                fresh_attempt_index = int(attempt_index)
            if int(attempt_index) != int(fresh_attempt_index):
                return
            _update_approach_memory(fresh_attempt_approach_memory, payload)

        def _fresh_attempt_approach_kwargs() -> dict[str, Any]:
            return _approach_progress_snapshot_kwargs(
                fresh_attempt_approach_memory,
                field_name="fresh_attempt_approach",
            )
        def _ownership_kwargs(payload: dict[str, Any] | None) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return {}
            return {
                "handoff_kind": clean_text(payload.get("handoff_kind"), clean_text(active_handoff_kind, "unspecified")),
                "zone_edge_correction_count": int(payload.get("zone_edge_correction_count", 0) or 0),
                "place_controller_reentry_count": int(place_controller_reentry_count),
                "post_visit_revisit_count": int(post_visit_revisit_count),
            }

        def _settle_kwargs(payload: dict[str, Any] | None) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return {}
            zone_payload = payload.get("zone_score", {}) if isinstance(payload.get("zone_score"), dict) else {}
            settle_metrics = payload.get("settle_metrics", {}) if isinstance(payload.get("settle_metrics"), dict) else {}
            final_inside_retrieval_corral = bool(
                settle_metrics.get("final_inside_retrieval_corral", zone_payload.get("center_inside_retrieval_corral", False))
            )
            final_center_inside_zone = bool(
                settle_metrics.get("final_center_inside_zone", zone_payload.get("center_inside_zone", False))
            )
            ball_stopped_in_corral = bool(settle_metrics.get("ball_stopped_in_corral", False))
            rolled_away_after_release = bool(settle_metrics.get("rolled_away_after_release", payload.get("rolled_away_after_release", False)))
            settled_pass = bool(settle_metrics.get("settled_in_corral_pass", payload.get("settled_in_corral_pass", False)))
            return {
                "final_inside_retrieval_corral": final_inside_retrieval_corral,
                "final_center_inside_zone": final_center_inside_zone,
                "ball_stopped_in_corral": ball_stopped_in_corral,
                "rolled_away_after_release": rolled_away_after_release,
                "settled_in_corral_pass": settled_pass,
                "practical_retrieval_pass": (
                    final_inside_retrieval_corral
                    and not rolled_away_after_release
                    and post_visit_revisit_count == 0
                ),
                "settle_exit_reason": clean_text(
                    payload.get("settle_exit_reason"),
                    clean_text(
                        settle_metrics.get("settle_exit_reason") if isinstance(settle_metrics, dict) else "",
                        default_settle_exit_reason(
                            failure_reason=str(payload.get("failure_reason", "")),
                            settled_in_corral_pass=settled_pass,
                            corrected=bool(
                                int(payload.get("zone_edge_correction_count", 0) or 0)
                                or int(place_controller_reentry_count)
                                or int(settle_metrics.get("release_recontact_count", 0) or 0)
                            ),
                            rolled_away_after_release=rolled_away_after_release,
                        ),
                    ),
                ),
            }

        def _normalize_post_visit_capture_failure(payload: dict[str, Any]) -> dict[str, Any]:
            zone_payload = payload.get("zone_score", {}) if isinstance(payload.get("zone_score"), dict) else {}
            correction_eligible = bool(payload.get("zone_edge_correction_eligible", False))
            final_inside_retrieval_corral = bool(zone_payload.get("center_inside_retrieval_corral", False))
            final_center_inside_zone = bool(zone_payload.get("center_inside_zone", False))
            rolled_away_after_release = not correction_eligible and not final_inside_retrieval_corral
            failure_reason = "release_roll_away" if rolled_away_after_release else "release_unsettled"
            return {
                **payload,
                "failure_reason": failure_reason,
                "failure_stage": "release",
                "allow_full_revisit": False,
                "final_inside_retrieval_corral": final_inside_retrieval_corral,
                "final_center_inside_zone": final_center_inside_zone,
                "ball_stopped_in_corral": False,
                "rolled_away_after_release": rolled_away_after_release,
                "settled_in_corral_pass": False,
                "settle_exit_reason": default_settle_exit_reason(
                    failure_reason=failure_reason,
                    rolled_away_after_release=rolled_away_after_release,
                ),
            }

        def _mark_fetch_objective_complete(final_ball_pose: dict[str, Any], shot_outcome: dict[str, Any]) -> None:
            if final_ball_pose:
                self._record_target_position(
                    target.id,
                    x=float(final_ball_pose.get("x", 0.0)),
                    y=float(final_ball_pose.get("y", 0.0)),
                    z=float(final_ball_pose.get("z", target.z_m) or target.z_m),
                )
            placed_targets = list(self.gather_runtime_state.get("placed_targets", []))
            if target.id not in placed_targets:
                placed_targets.append(target.id)
            fetched_targets = list(self.gather_runtime_state.get("fetched_targets", []))
            if target.id not in fetched_targets:
                fetched_targets.append(target.id)
            visited_targets = list(self.visit_runtime_state.get("visited_targets", []))
            if target.id not in visited_targets:
                visited_targets.append(target.id)
            remaining_targets = [item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id]
            self._update_gather_runtime_state(
                mission_phase="advance",
                gather_phase="advance",
                placed_targets=placed_targets,
                fetched_targets=fetched_targets,
                remaining_targets=remaining_targets,
                capture_loss_count=capture_loss_count,
                latest_feedback=f"{target.label} fetched through the delivery pose.",
                last_fetch_to_pose_result=shot_outcome,
            )
            self._update_visit_runtime_state(
                visited_targets=visited_targets,
                remaining_targets=remaining_targets,
                last_visit_result={"target_id": target.id, "pass": True, "mission_objective": self.mission_objective},
                current_target_prior={},
                mission_phase="advance",
                latest_feedback=f"{target.label} fetched through the delivery pose.",
            )
            self._append_runtime_event(
                f"{target.label} fetched through the delivery pose.",
                key=f"fetch_to_pose:{target.id}",
            )

        def _resolve_fetch_to_pose_place_result(
            *,
            place_pass: bool,
            place_payload: dict[str, Any],
            capture_payload: dict[str, Any],
            attempt_kind: str,
            local_recovery_attempted: bool,
            terminal_failure: bool,
        ) -> dict[str, Any] | None:
            if self.mission_objective != MISSION_OBJECTIVE_FETCH_TO_POSE:
                return None
            if not place_pass and not terminal_failure:
                return None
            place_failure_reason = "" if place_pass else str(place_payload.get("failure_reason", "place_failed"))
            final_ball_pose = pose_payload(place_payload.get("final_ball_pose"))
            shot_outcome = self._build_fetch_to_pose_outcome(
                target=target,
                state_history_path=state_history_path,
                final_ball_pose=final_ball_pose,
                place_payload=place_payload,
                place_failure_reason=place_failure_reason,
            )
            fetch_pose_world = shot_outcome.get("fetch_pose_world", {}) if isinstance(shot_outcome.get("fetch_pose_world"), dict) else {}
            final_ball_pose = pose_payload(shot_outcome.get("ball_end_pose")) or final_ball_pose
            fetch_to_pose_reached = bool(shot_outcome.get("pass", False))
            fetch_failure_reason = "" if fetch_to_pose_reached else clean_text(shot_outcome.get("reason"), "fetch_to_pose_missed")
            fetch_elapsed_s = clean_number(place_payload.get("fetch_elapsed_s"))
            fetch_time_s = float(fetch_elapsed_s) if fetch_elapsed_s is not None else time.monotonic() - target_start_monotonic
            fetch_fields = {
                "fetch_to_pose_reached": fetch_to_pose_reached,
                "fetch_to_pose_time_s": fetch_time_s,
                "fetch_to_pose_failure_reason": fetch_failure_reason,
                "fetch_pose_world": fetch_pose_world,
                "shot_outcome": shot_outcome,
            }
            fetch_result_row = {
                "generated_utc": utc_now(),
                "event_type": "fetch_to_pose_result",
                "phase": "fetch_to_pose",
                "target_id": target.id,
                "attempt": int(attempt),
                "attempt_kind": attempt_kind,
                "fetch_to_pose": {
                    "pass": fetch_to_pose_reached,
                    "reached": fetch_to_pose_reached,
                    "time_s": round(float(fetch_time_s), 6),
                    "distance_to_fetch_pose_m": shot_outcome.get("distance_to_fetch_pose_m"),
                    "closest_approach_distance_m": shot_outcome.get("closest_approach_distance_m"),
                    "failure_reason": fetch_failure_reason,
                },
                "fetch_pose_world": fetch_pose_world,
                "shot_outcome": shot_outcome,
            }
            append_jsonl(state_history_path, fetch_result_row)
            append_jsonl(gather_sequence_path, fetch_result_row)

            settle_metrics = place_payload.get("settle_metrics") if isinstance(place_payload.get("settle_metrics"), dict) else None
            if fetch_to_pose_reached:
                _mark_fetch_objective_complete(final_ball_pose, shot_outcome)
                return self._target_success_result(
                    target=target,
                    attempts=attempt,
                    capture_loss_count=capture_loss_count,
                    route_index=route_index,
                    final_ball_pose=final_ball_pose,
                    place_time_s=fetch_time_s,
                    attempt_kind=attempt_kind,
                    local_recovery_attempted=local_recovery_attempted,
                    revisit_attempted=post_visit_revisit_count > 0,
                    settle_metrics=settle_metrics,
                    handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                    zone_edge_correction_count=zone_edge_correction_count,
                    place_controller_reentry_count=place_controller_reentry_count,
                    post_visit_revisit_count=post_visit_revisit_count,
                    **fetch_fields,
                    **_retention_kwargs(place_payload),
                    **_settle_kwargs(place_payload),
                    **_control_diag_kwargs(place_payload),
                    **_approach_kwargs(capture_payload),
                    **_latest_approach_progress_kwargs(),
                    **_fresh_attempt_approach_kwargs(),
                )

            self._update_visit_runtime_state(
                proof_state="failed",
                mission_phase="failed",
                latest_feedback=f"{target.label} fetch-to-pose missed.",
            )
            return self._target_failure_result(
                target=target,
                failure_reason=fetch_failure_reason,
                failure_stage="fetch_to_pose",
                attempts=attempt,
                capture_loss_count=capture_loss_count,
                route_index=route_index,
                attempt_kind=attempt_kind,
                local_recovery_attempted=local_recovery_attempted,
                revisit_attempted=post_visit_revisit_count > 0,
                settle_metrics=settle_metrics,
                handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                zone_edge_correction_count=zone_edge_correction_count,
                place_controller_reentry_count=place_controller_reentry_count,
                post_visit_revisit_count=post_visit_revisit_count,
                **fetch_fields,
                **_retention_kwargs(place_payload),
                **_settle_kwargs(place_payload),
                **_control_diag_kwargs(place_payload),
                **_approach_kwargs(capture_payload),
                **_latest_approach_progress_kwargs(),
                **_fresh_attempt_approach_kwargs(),
            )

        while attempt <= self.args.max_retries_per_target:
            attempt += 1
            direct_recapture_attempt = resume_with_capture
            place_controller_reentry_attempt = resume_with_place_controller
            place_loss_revisit_attempt = resume_with_place_loss_revisit
            fresh_approach_retry_attempt = resume_with_fresh_approach
            force_local_capture_attempt = bool(
                visit_completed_once
                and not place_controller_reentry_attempt
                and not direct_recapture_attempt
                and not place_loss_revisit_attempt
                and not fresh_approach_retry_attempt
            )
            resume_with_capture = False
            resume_with_place_controller = False
            resume_with_place_loss_revisit = False
            resume_with_fresh_approach = False

            if place_controller_reentry_attempt:
                attempt_kind = "place_controller_reentry"
            elif direct_recapture_attempt or force_local_capture_attempt:
                attempt_kind = "place_loss_recapture"
            elif place_loss_revisit_attempt:
                attempt_kind = "place_loss_revisit"
            else:
                attempt_kind = "initial_visit" if not visit_completed_once else "retry_visit"
            enable_goal_side_stage = attempt_kind in {"initial_visit", "retry_visit", "place_loss_revisit"}

            if place_controller_reentry_attempt:
                place_controller_reentry_count += 1
                self._append_runtime_event(
                    f"{target.label}: place controller reentry {place_controller_reentry_count} near the corral edge.",
                    key=f"place_controller_reentry:{target.id}:{place_controller_reentry_count}",
                )
                self._update_visit_runtime_state(
                    proof_state="placing",
                    current_target_id=target.id,
                    visit_index=route_index,
                    remaining_targets=[item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id],
                    mission_phase="place",
                    latest_feedback=f"Continuing local place correction for {target.label}.",
                )
                self._update_gather_runtime_state(
                    mission_phase="place",
                    gather_phase="place",
                    current_target_id=target.id,
                    visit_index=route_index,
                    latest_feedback=f"Continuing local place correction for {target.label}.",
                )
            elif direct_recapture_attempt:
                self._append_runtime_event(
                    f"{target.label}: direct recapture attempt {place_loss_recapture_count} after place-stage loss.",
                    key=f"place_loss_recapture:{target.id}:{place_loss_recapture_count}",
                )
                self._update_visit_runtime_state(
                    proof_state="capturing",
                    current_target_id=target.id,
                    visit_index=route_index,
                    remaining_targets=[item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id],
                    mission_phase="capture",
                    latest_feedback=f"Reacquiring {target.label} after place-stage loss.",
                )
                self._update_gather_runtime_state(
                    mission_phase="capture",
                    gather_phase="capture",
                    current_target_id=target.id,
                    visit_index=route_index,
                    latest_feedback=f"Reacquiring {target.label} after place-stage loss.",
                )
                ball_pose = self._ball_truth_pose(session_id, target)
                if ball_pose:
                    self._update_prior_from_ball_pose(target.id, ball_pose)
            elif force_local_capture_attempt:
                self._append_runtime_event(
                    f"{target.label}: skipping redundant revisit after the first visit; keeping gather ownership.",
                    key=f"skip_revisit:{target.id}:{attempt}",
                )
                self._update_visit_runtime_state(
                    proof_state="capturing",
                    current_target_id=target.id,
                    visit_index=route_index,
                    remaining_targets=[item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id],
                    mission_phase="capture",
                    latest_feedback=f"Keeping gather ownership for {target.label} after the first visit.",
                )
                self._update_gather_runtime_state(
                    mission_phase="capture",
                    gather_phase="capture",
                    current_target_id=target.id,
                    visit_index=route_index,
                    latest_feedback=f"Keeping gather ownership for {target.label} after the first visit.",
                )
                ball_pose = self._ball_truth_pose(session_id, target)
                if ball_pose:
                    self._update_prior_from_ball_pose(target.id, ball_pose)
            else:
                if place_loss_revisit_attempt:
                    if visit_completed_once:
                        post_visit_revisit_count += 1
                    self._append_runtime_event(
                        f"{target.label}: full revisit {post_visit_revisit_count or place_loss_full_revisit_count} after place-stage loss.",
                        key=f"place_loss_revisit:{target.id}:{post_visit_revisit_count or place_loss_full_revisit_count}",
                    )
                    visit_feedback = f"Revisiting {target.label} after place-stage loss."
                else:
                    self._append_runtime_event(f"{target.label}: pre-stage attempt {attempt}.", key=f"pre_stage_attempt:{target.id}:{attempt}")
                    visit_feedback = f"Navigating behind {target.label} before staging."
                self._update_visit_runtime_state(
                    proof_state="visiting",
                    current_target_id=target.id,
                    visit_index=route_index,
                    remaining_targets=[item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id],
                    mission_phase="pre_stage",
                    latest_feedback=visit_feedback,
                )
                self._update_gather_runtime_state(
                    mission_phase="pre_stage",
                    gather_phase="pre_stage",
                    current_target_id=target.id,
                    visit_index=route_index,
                    latest_feedback=visit_feedback,
                )
                ball_pose = self._ball_truth_pose(session_id, target)
                if ball_pose:
                    self._update_prior_from_ball_pose(target.id, ball_pose)
                pre_stage_pass, pre_stage_payload = self._pre_stage_target(
                    session_id=session_id,
                    target=target,
                    state_history_path=state_history_path,
                    mission_root=mission_root,
                    attempt_index=attempt,
                    attempt_kind=attempt_kind,
                )
                _approach_kwargs(pre_stage_payload)
                _record_fresh_attempt_approach(pre_stage_payload, attempt_index=attempt, attempt_kind=attempt_kind)
                append_jsonl(
                    gather_sequence_path,
                    {
                        "generated_utc": utc_now(),
                        "event_type": "pre_stage_result",
                        "target_id": target.id,
                        "attempt": attempt,
                        "status": "pre_stage_pass" if pre_stage_pass else str(pre_stage_payload.get("failure_reason", "pre_stage_failed")),
                        "pass": pre_stage_pass,
                    },
                )
                if not pre_stage_pass:
                    if attempt > self.args.max_retries_per_target:
                        self._update_visit_runtime_state(proof_state="failed", mission_phase="failed", latest_feedback=f"{target.label} pre-stage failed.")
                        return self._target_failure_result(
                            target=target,
                            failure_reason=str(pre_stage_payload.get("failure_reason", "pre_stage_failed")),
                            failure_stage=str(pre_stage_payload.get("failure_stage", "pre_stage")),
                            attempts=attempt,
                            capture_loss_count=capture_loss_count,
                            route_index=route_index,
                            attempt_kind=attempt_kind,
                            local_recovery_attempted=local_recovery_attempted_any,
                            revisit_attempted=post_visit_revisit_count > 0,
                            handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                            zone_edge_correction_count=zone_edge_correction_count,
                            place_controller_reentry_count=place_controller_reentry_count,
                            post_visit_revisit_count=post_visit_revisit_count,
                            **_approach_kwargs(pre_stage_payload),
                            **_latest_approach_progress_kwargs(),
                            **_fresh_attempt_approach_kwargs(),
                        )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    continue
                visit_completed_once = True
                self._append_runtime_event(
                    f"{target.label}: pre-stage arrival complete; handing off to goal-side staging.",
                    key=f"pre_stage_handoff:{target.id}:{attempt}",
                )
                self._safe_stop()
                self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
            capture_payload: dict[str, Any] = {}
            capture_pass = True
            if not place_controller_reentry_attempt:
                capture_pass, capture_payload = self._capture_target(
                    session_id=session_id,
                    target=target,
                    state_history_path=state_history_path,
                    mission_root=mission_root,
                    prefer_zone_recovery=direct_recapture_attempt or force_local_capture_attempt,
                    enable_goal_side_stage=enable_goal_side_stage,
                    attempt_index=attempt,
                    attempt_kind=attempt_kind,
                )
                _approach_kwargs(capture_payload)
                _record_fresh_attempt_approach(capture_payload, attempt_index=attempt, attempt_kind=attempt_kind)
                if not capture_pass:
                    capture_failure_reason = str(capture_payload.get("failure_reason", "capture_failed"))
                    capture_failure_stage = str(capture_payload.get("failure_stage", "capture"))
                    zone_edge_correction_count += int(capture_payload.get("zone_edge_correction_count", 0) or 0)
                    if capture_failure_stage in {"stage", "capture_entry"}:
                        if attempt > self.args.max_retries_per_target:
                            self._update_visit_runtime_state(
                                proof_state="failed",
                                mission_phase="failed",
                                latest_feedback=f"{target.label} fresh approach failed.",
                            )
                            return self._target_failure_result(
                                target=target,
                                failure_reason=capture_failure_reason,
                                failure_stage=capture_failure_stage,
                                attempts=attempt,
                                capture_loss_count=capture_loss_count,
                                route_index=route_index,
                                attempt_kind=attempt_kind,
                                local_recovery_attempted=local_recovery_attempted_any,
                                revisit_attempted=post_visit_revisit_count > 0,
                                handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                                zone_edge_correction_count=zone_edge_correction_count,
                                place_controller_reentry_count=place_controller_reentry_count,
                                post_visit_revisit_count=post_visit_revisit_count,
                                **_approach_kwargs(capture_payload),
                                **_latest_approach_progress_kwargs(),
                                **_fresh_attempt_approach_kwargs(),
                            )
                        self._append_runtime_event(
                            f"{target.label}: fresh approach {capture_failure_stage} failed; retrying behind-ball arrival.",
                            key=f"fresh_approach_retry:{target.id}:{attempt}:{capture_failure_stage}",
                        )
                        self._safe_stop()
                        self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                        resume_with_fresh_approach = True
                        continue
                    if direct_recapture_attempt and attempt <= self.args.max_retries_per_target:
                        place_loss_recapture_count += 1
                        self._append_runtime_event(
                            f"{target.label}: keeping place ownership after place-stage recapture timeout {place_loss_recapture_count}.",
                            key=f"place_controller_hold:{target.id}:{place_loss_recapture_count}:{capture_failure_reason}",
                        )
                        self._safe_stop()
                        self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                        resume_with_place_controller = True
                        continue
                    if visit_completed_once and attempt <= self.args.max_retries_per_target:
                        place_loss_recapture_count += 1
                        self._append_runtime_event(
                            f"{target.label}: local gather recapture after post-visit capture timeout {place_loss_recapture_count}.",
                            key=f"post_visit_capture_recapture:{target.id}:{place_loss_recapture_count}",
                        )
                        self._safe_stop()
                        self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                        resume_with_capture = True
                        continue
                    if visit_completed_once:
                        capture_failure_reason = str(
                            _normalize_post_visit_capture_failure(capture_payload).get("failure_reason", capture_failure_reason)
                        )
                        capture_failure_stage = str(
                            _normalize_post_visit_capture_failure(capture_payload).get("failure_stage", capture_failure_stage)
                        )
                    if attempt > self.args.max_retries_per_target or place_loss_full_revisit_count > 0 or visit_completed_once:
                        normalized_capture_failure = (
                            _normalize_post_visit_capture_failure(capture_payload)
                            if visit_completed_once
                            else capture_payload
                        )
                        self._update_visit_runtime_state(proof_state="failed", mission_phase="failed", latest_feedback=f"{target.label} capture failed.")
                        return self._target_failure_result(
                            target=target,
                            failure_reason=capture_failure_reason,
                            failure_stage=capture_failure_stage,
                            attempts=attempt,
                            capture_loss_count=capture_loss_count,
                            route_index=route_index,
                            attempt_kind=attempt_kind,
                            local_recovery_attempted=local_recovery_attempted_any,
                            revisit_attempted=post_visit_revisit_count > 0,
                            settle_metrics=normalized_capture_failure.get("settle_metrics") if isinstance(normalized_capture_failure.get("settle_metrics"), dict) else None,
                            handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                            zone_edge_correction_count=zone_edge_correction_count,
                            place_controller_reentry_count=place_controller_reentry_count,
                            post_visit_revisit_count=post_visit_revisit_count,
                            **_retention_kwargs(normalized_capture_failure),
                            **_settle_kwargs(normalized_capture_failure),
                            **_control_diag_kwargs(normalized_capture_failure),
                            **_approach_kwargs(normalized_capture_failure),
                            **_latest_approach_progress_kwargs(),
                            **_fresh_attempt_approach_kwargs(),
                        )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    continue
                active_handoff_kind = clean_text(
                    capture_payload.get("handoff_kind"),
                    "zone_entry"
                    if bool(capture_payload.get("entered_zone_during_capture"))
                    else "soft_capture"
                    if bool(capture_payload.get("soft_capture_handoff"))
                    else "secure_capture",
                )
                if direct_recapture_attempt:
                    place_controller_reentry_count += 1

            if isinstance(capture_payload.get("final_ball_pose"), dict):
                fetch_resolution = _resolve_fetch_to_pose_place_result(
                    place_pass=True,
                    place_payload=capture_payload,
                    capture_payload=capture_payload,
                    attempt_kind=attempt_kind,
                    local_recovery_attempted=local_recovery_attempted_any,
                    terminal_failure=False,
                )
                if fetch_resolution is not None:
                    return fetch_resolution
                final_ball_pose = capture_payload.get("final_ball_pose", {})
                if final_ball_pose:
                    self._record_target_position(
                        target.id,
                        x=float(final_ball_pose.get("x", 0.0)),
                        y=float(final_ball_pose.get("y", 0.0)),
                        z=float(final_ball_pose.get("z", target.z_m) or target.z_m),
                    )
                placed_targets = list(self.gather_runtime_state.get("placed_targets", []))
                if target.id not in placed_targets:
                    placed_targets.append(target.id)
                visited_targets = list(self.visit_runtime_state.get("visited_targets", []))
                if target.id not in visited_targets:
                    visited_targets.append(target.id)
                remaining_targets = [item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id]
                self._update_gather_runtime_state(
                    mission_phase="advance",
                    gather_phase="advance",
                    placed_targets=placed_targets,
                    remaining_targets=remaining_targets,
                    capture_loss_count=capture_loss_count,
                    latest_feedback=f"{target.label} placed in the zone.",
                )
                self._update_visit_runtime_state(
                    visited_targets=visited_targets,
                    remaining_targets=remaining_targets,
                    last_visit_result={"target_id": target.id, "pass": True},
                    current_target_prior={},
                    mission_phase="advance",
                    latest_feedback=f"{target.label} placed in the zone.",
                )
                self._append_runtime_event(f"{target.label} placed in the corral zone.", key=f"placed:{target.id}")
                settle_metrics = capture_payload.get("settle_metrics") if isinstance(capture_payload.get("settle_metrics"), dict) else None
                if settle_metrics is None and final_ball_pose:
                    zone_score = zone_snapshot(final_ball_pose, self.zone)
                    if zone_score is not None:
                        settle_metrics = summarize_release_settle_trace(
                            surface_profile=self.surface_profile,
                            zone=self.zone,
                            release_samples=[
                                self._release_sample(
                                    release_started_monotonic=target_start_monotonic,
                                    now_monotonic=time.monotonic(),
                                    ball_pose=final_ball_pose,
                                    zone_score=zone_score,
                                )
                            ],
                            release_recontact_count=0,
                        ).to_dict()
                return self._target_success_result(
                    target=target,
                    attempts=attempt,
                    capture_loss_count=capture_loss_count,
                    route_index=route_index,
                    final_ball_pose=final_ball_pose,
                    place_time_s=time.monotonic() - target_start_monotonic,
                    attempt_kind=attempt_kind,
                    revisit_attempted=post_visit_revisit_count > 0,
                    settle_metrics=settle_metrics,
                    handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                    zone_edge_correction_count=zone_edge_correction_count,
                    place_controller_reentry_count=place_controller_reentry_count,
                    post_visit_revisit_count=post_visit_revisit_count,
                    **_retention_kwargs(capture_payload),
                    **_settle_kwargs(capture_payload),
                    **_control_diag_kwargs(capture_payload),
                    **_approach_kwargs(capture_payload),
                    **_latest_approach_progress_kwargs(),
                    **_fresh_attempt_approach_kwargs(),
                )

            if self.mission_objective == MISSION_OBJECTIVE_FETCH_TO_POSE:
                fetch_pass, fetch_payload = self._fetch_to_pose_target(
                    session_id=session_id,
                    target=target,
                    state_history_path=state_history_path,
                    attempt_index=attempt,
                    attempt_kind=attempt_kind,
                )
                fetch_resolution = _resolve_fetch_to_pose_place_result(
                    place_pass=fetch_pass,
                    place_payload=fetch_payload,
                    capture_payload=capture_payload,
                    attempt_kind=attempt_kind,
                    local_recovery_attempted=local_recovery_attempted_any,
                    terminal_failure=True,
                )
                if fetch_resolution is not None:
                    return fetch_resolution

            place_pass, place_payload = self._place_target(
                session_id=session_id,
                target=target,
                state_history_path=state_history_path,
                attempt_index=attempt,
                attempt_kind=attempt_kind,
            )
            zone_edge_correction_count += int(place_payload.get("zone_edge_correction_count", 0) or 0)
            failure_reason = str(place_payload.get("failure_reason", "place_failed")) if not place_pass else ""
            failure_stage = str(place_payload.get("failure_stage", "place")) if not place_pass else ""
            local_recovery_attempted = bool(place_payload.get("local_recovery_attempted", False))
            local_recovery_attempted_any = local_recovery_attempted_any or local_recovery_attempted
            place_recovery_failure = failure_reason in {"capture_lost", "release_unsettled", "release_roll_away"}
            if failure_reason == "capture_lost":
                capture_loss_count += 1
                self._update_gather_runtime_state(capture_loss_count=capture_loss_count)
            fetch_resolution = _resolve_fetch_to_pose_place_result(
                place_pass=place_pass,
                place_payload=place_payload,
                capture_payload=capture_payload,
                attempt_kind=attempt_kind,
                local_recovery_attempted=local_recovery_attempted_any or bool(place_payload.get("local_recovery_attempted", False)),
                terminal_failure=bool(
                    failure_reason == "release_roll_away"
                    or attempt > self.args.max_retries_per_target
                    or (not place_recovery_failure and not place_pass and attempt > self.args.max_retries_per_target)
                ),
            )
            if fetch_resolution is not None:
                return fetch_resolution
            if place_pass:
                final_ball_pose = place_payload.get("final_ball_pose") if isinstance(place_payload.get("final_ball_pose"), dict) else {}
                if final_ball_pose:
                    self._record_target_position(
                        target.id,
                        x=float(final_ball_pose.get("x", 0.0)),
                        y=float(final_ball_pose.get("y", 0.0)),
                        z=float(final_ball_pose.get("z", target.z_m) or target.z_m),
                    )
                placed_targets = list(self.gather_runtime_state.get("placed_targets", []))
                if target.id not in placed_targets:
                    placed_targets.append(target.id)
                visited_targets = list(self.visit_runtime_state.get("visited_targets", []))
                if target.id not in visited_targets:
                    visited_targets.append(target.id)
                remaining_targets = [item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id]
                self._update_gather_runtime_state(
                    mission_phase="advance",
                    gather_phase="advance",
                    placed_targets=placed_targets,
                    remaining_targets=remaining_targets,
                    capture_loss_count=capture_loss_count,
                    latest_feedback=f"{target.label} placed in the zone.",
                )
                self._update_visit_runtime_state(
                    visited_targets=visited_targets,
                    remaining_targets=remaining_targets,
                    last_visit_result={"target_id": target.id, "pass": True},
                    current_target_prior={},
                    mission_phase="advance",
                    latest_feedback=f"{target.label} placed in the zone.",
                )
                self._append_runtime_event(f"{target.label} placed in the corral zone.", key=f"placed:{target.id}")
                settle_metrics = place_payload.get("settle_metrics") if isinstance(place_payload.get("settle_metrics"), dict) else None
                return self._target_success_result(
                    target=target,
                    attempts=attempt,
                    capture_loss_count=capture_loss_count,
                    route_index=route_index,
                    final_ball_pose=final_ball_pose,
                    place_time_s=time.monotonic() - target_start_monotonic,
                    attempt_kind=attempt_kind,
                    local_recovery_attempted=local_recovery_attempted_any or bool(place_payload.get("local_recovery_attempted", False)),
                    revisit_attempted=post_visit_revisit_count > 0,
                    settle_metrics=settle_metrics,
                    handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                    zone_edge_correction_count=zone_edge_correction_count,
                    place_controller_reentry_count=place_controller_reentry_count,
                    post_visit_revisit_count=post_visit_revisit_count,
                    **_retention_kwargs(place_payload),
                    **_settle_kwargs(place_payload),
                    **_control_diag_kwargs(place_payload),
                    **_approach_kwargs(capture_payload),
                    **_latest_approach_progress_kwargs(),
                    **_fresh_attempt_approach_kwargs(),
                )

            if place_recovery_failure:
                recovery_label = "place-stage correction" if failure_reason == "capture_lost" else "release-stage correction"
                if failure_reason != "release_roll_away" and attempt <= self.args.max_retries_per_target:
                    self._append_runtime_event(
                        f"{target.label}: keeping place ownership during {recovery_label}.",
                        key=f"place_correction_reentry:{target.id}:{attempt}:{failure_reason}",
                    )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    resume_with_place_controller = True
                    continue
            if attempt > self.args.max_retries_per_target or place_recovery_failure:
                self._update_visit_runtime_state(proof_state="failed", mission_phase="failed", latest_feedback=f"{target.label} place failed.")
                return self._target_failure_result(
                    target=target,
                    failure_reason=failure_reason,
                    failure_stage=failure_stage,
                    attempts=attempt,
                    capture_loss_count=capture_loss_count,
                    route_index=route_index,
                    attempt_kind=attempt_kind,
                    local_recovery_attempted=local_recovery_attempted_any,
                    revisit_attempted=post_visit_revisit_count > 0,
                    settle_metrics=place_payload.get("settle_metrics") if isinstance(place_payload.get("settle_metrics"), dict) else None,
                    handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                    zone_edge_correction_count=zone_edge_correction_count,
                    place_controller_reentry_count=place_controller_reentry_count,
                    post_visit_revisit_count=post_visit_revisit_count,
                    **_retention_kwargs(place_payload),
                    **_settle_kwargs(place_payload),
                    **_control_diag_kwargs(place_payload),
                    **_approach_kwargs(capture_payload),
                    **_latest_approach_progress_kwargs(),
                    **_fresh_attempt_approach_kwargs(),
                )
            self._safe_stop()
            self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)

        return self._target_failure_result(
            target=target,
            failure_reason="unreachable_state",
            failure_stage="mission",
            attempts=attempt,
            capture_loss_count=capture_loss_count,
            route_index=route_index,
            attempt_kind="unreachable_state",
            revisit_attempted=post_visit_revisit_count > 0,
            settle_metrics={},
            clean_retention_pass=False,
            handoff_kind=clean_text(active_handoff_kind, "unspecified"),
            zone_edge_correction_count=zone_edge_correction_count,
            place_controller_reentry_count=place_controller_reentry_count,
            post_visit_revisit_count=post_visit_revisit_count,
            **_latest_approach_progress_kwargs(),
            **_fresh_attempt_approach_kwargs(),
        )

    def run(self) -> dict[str, Any]:
        ready_state, started_here = self._ensure_environment_ready()
        self._started_here = started_here
        ready_state = self._wait_for_robot_pose(timeout_s=self.args.environment_timeout_s)
        session_id = clean_text(ready_state.get("session_id"))
        if not session_id:
            raise RuntimeError("Dashboard did not provide a session id for gather mission.")

        mission_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / session_id / self.args.artifact_kind / current_utc_stamp())
        gather_sequence_path = mission_root / "gather_sequence.jsonl"
        state_history_path = mission_root / "state_history.jsonl"
        target_results_path = mission_root / "target_results.json"

        self._init_runtime_state(session_id=session_id, mission_root=mission_root)
        self._append_runtime_event(f"{self.args.scenario_label} mission started.", category="scenario", key="mission_started")
        self._safe_stop()
        self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
        self._spawn_mission_models(ready_state, mission_root)
        expected_truth_models = {self._target_model_name(target) for target in self.targets}
        self._wait_for_truth_models(session_id, expected_truth_models, timeout_s=30.0)
        self._start_motion_bridge(clean_text(ready_state.get("compose_project")), mission_root)

        target_results: list[dict[str, Any]] = []
        mission_pass = True
        mission_error = ""
        mission_started_monotonic = time.monotonic()

        try:
            remaining_ids = [item.id for item in self.targets]
            route_decisions: list[dict[str, Any]] = []
            route_index = 0
            while remaining_ids:
                state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
                ordered_ids = self._reuse_prior_route_order(remaining_ids, route_decisions)
                if not ordered_ids:
                    ordered_ids = self._plan_collection_route(remaining_ids, state)
                route_index += 1
                selected_id = ordered_ids[0]
                route_decisions.append({"step": route_index, "ordered_ids": ordered_ids, "selected_id": selected_id})
                self._update_gather_runtime_state(
                    route_order=[item["selected_id"] for item in route_decisions],
                    remaining_targets=list(remaining_ids),
                )
                append_jsonl(
                    gather_sequence_path,
                    {
                        "generated_utc": utc_now(),
                        "event_type": "route_planned",
                        "step": route_index,
                        "ordered_ids": ordered_ids,
                        "selected_id": selected_id,
                    },
                )
                target = self.targets_by_id[selected_id]
                target_result = self._run_target(
                    session_id=session_id,
                    target=target,
                    route_index=route_index,
                    gather_sequence_path=gather_sequence_path,
                    state_history_path=state_history_path,
                    mission_root=mission_root,
                )
                target_results.append(target_result)
                write_json(target_results_path, {"targets": target_results})
                remaining_ids = [item for item in remaining_ids if item != selected_id] if target_result.get("pass") else remaining_ids
                self._update_gather_runtime_state(
                    remaining_targets=remaining_ids,
                    mission_phase="advance" if target_result.get("pass") else "failed",
                    mission_status="running" if target_result.get("pass") else "failed",
                )
                self._update_visit_runtime_state(
                    remaining_targets=remaining_ids,
                    last_visit_result=target_result,
                    mission_status="running" if target_result.get("pass") else "failed",
                    mission_phase="advance" if target_result.get("pass") else "failed",
                    proof_state="placing" if target_result.get("pass") else "failed",
                )
                append_jsonl(
                    gather_sequence_path,
                    {
                        "generated_utc": utc_now(),
                        "event_type": "target_completed",
                        "target_id": selected_id,
                        "result": target_result,
                    },
                )
                if not target_result.get("pass"):
                    mission_pass = False
                    mission_error = str(target_result.get("failure_reason", "target_failed"))
                    self._append_runtime_event(
                        f"{target.label} failed: {mission_error}",
                        category="error",
                        key=f"target_failed:{target.id}",
                    )
                    break
                self._safe_stop()
                self._wait_for_pursuit_quiet(self._inter_target_quiet_timeout_s())

            mission_time_s = round(time.monotonic() - mission_started_monotonic, 6)
            placed_targets = list(self.gather_runtime_state.get("placed_targets", []))
            capture_loss_count = int(self.gather_runtime_state.get("capture_loss_count", 0) or 0)
            mission_completed_pass = mission_pass and len(placed_targets) == len(self.targets)
            final_result = next((item for item in reversed(target_results) if isinstance(item, dict)), {})
            stopped_with_ball_captured = bool(final_result.get("stopped_with_ball_captured", False))
            release_started_with_capture = bool(final_result.get("release_started_with_capture", False))
            stop_capture_state = final_result.get("stop_capture_state", {}) if isinstance(final_result.get("stop_capture_state"), dict) else {}
            release_capture_state = final_result.get("release_capture_state", {}) if isinstance(final_result.get("release_capture_state"), dict) else {}
            clean_retention_pass = (
                mission_completed_pass
                and capture_loss_count == 0
                and stopped_with_ball_captured
                and release_started_with_capture
            )
            handoff_kind = clean_text(final_result.get("handoff_kind"), "unspecified")
            zone_edge_correction_count = sum(int(item.get("zone_edge_correction_count", 0) or 0) for item in target_results)
            place_controller_reentry_count = sum(int(item.get("place_controller_reentry_count", 0) or 0) for item in target_results)
            post_visit_revisit_count = sum(int(item.get("post_visit_revisit_count", 0) or 0) for item in target_results)
            settle_exit_reason = clean_text(final_result.get("settle_exit_reason"))
            settle_no_chase_activated = bool(final_result.get("settle_no_chase_activated", False))
            settle_no_chase_exit_reason = clean_text(final_result.get("settle_no_chase_exit_reason"), "none")
            release_gate_blocked_reason = clean_text(final_result.get("release_gate_blocked_reason"), "none")
            pre_stage_pose_world = (
                final_result.get("pre_stage_pose_world", {})
                if isinstance(final_result.get("pre_stage_pose_world"), dict)
                else {}
            )
            pre_stage_pose_reached = bool(final_result.get("pre_stage_pose_reached", False))
            pre_stage_time_s = float(clean_number(final_result.get("pre_stage_time_s")) or 0.0)
            pre_stage_handoff_pass = bool(final_result.get("pre_stage_handoff_pass", False))
            approach_side_verdict = (
                final_result.get("approach_side_verdict", {})
                if isinstance(final_result.get("approach_side_verdict"), dict)
                else {}
            )
            staging_pose_reached = bool(final_result.get("staging_pose_reached", False))
            entered_goal_side_before_capture = bool(final_result.get("entered_goal_side_before_capture", False))
            first_contact_push_alignment = clean_number(final_result.get("first_contact_push_alignment_deg"))
            push_direction_yaw_deg = float(clean_number(final_result.get("push_direction_yaw_deg")) or 0.0)
            stage_time_s = float(clean_number(final_result.get("stage_time_s")) or 0.0)
            capture_entry_reached = bool(final_result.get("capture_entry_reached", False))
            capture_entry_time_s = float(clean_number(final_result.get("capture_entry_time_s")) or 0.0)
            approach_failure_reason = clean_text(final_result.get("approach_failure_reason"))
            fresh_attempt_approach = (
                final_result.get("fresh_attempt_approach", {})
                if isinstance(final_result.get("fresh_attempt_approach"), dict)
                else {}
            )
            latest_approach_progress = (
                final_result.get("latest_approach_progress", {})
                if isinstance(final_result.get("latest_approach_progress"), dict)
                else {}
            )
            approach_fields = resolve_approach_result_fields(
                pre_stage_pose_world=pre_stage_pose_world,
                pre_stage_pose_reached=pre_stage_pose_reached,
                pre_stage_time_s=pre_stage_time_s,
                pre_stage_handoff_pass=pre_stage_handoff_pass,
                approach_side_verdict=approach_side_verdict,
                staging_pose_reached=staging_pose_reached,
                entered_goal_side_before_capture=entered_goal_side_before_capture,
                first_contact_push_alignment_deg=first_contact_push_alignment,
                push_direction_yaw_deg=push_direction_yaw_deg,
                stage_time_s=stage_time_s,
                capture_entry_reached=capture_entry_reached,
                capture_entry_time_s=capture_entry_time_s,
                approach_failure_reason=approach_failure_reason,
                latest_approach_progress=latest_approach_progress,
                fresh_attempt_approach=fresh_attempt_approach,
            )
            pre_stage_pose_world = dict(approach_fields["pre_stage_pose_world"])
            pre_stage_pose_reached = bool(approach_fields["pre_stage_pose_reached"])
            pre_stage_time_s = float(approach_fields["pre_stage_time_s"])
            pre_stage_handoff_pass = bool(approach_fields["pre_stage_handoff_pass"])
            approach_side_verdict = dict(approach_fields["approach_side_verdict"])
            staging_pose_reached = bool(approach_fields["staging_pose_reached"])
            entered_goal_side_before_capture = bool(approach_fields["entered_goal_side_before_capture"])
            first_contact_push_alignment = clean_number(approach_fields["first_contact_push_alignment_deg"])
            push_direction_yaw_deg = float(approach_fields["push_direction_yaw_deg"])
            stage_time_s = float(approach_fields["stage_time_s"])
            capture_entry_reached = bool(approach_fields["capture_entry_reached"])
            capture_entry_time_s = float(approach_fields["capture_entry_time_s"])
            approach_failure_reason = clean_text(approach_fields["approach_failure_reason"])
            final_inside_retrieval_corral = bool(final_result.get("final_inside_retrieval_corral", False))
            final_center_inside_zone = bool(final_result.get("final_center_inside_zone", False))
            ball_stopped_in_corral = bool(final_result.get("ball_stopped_in_corral", False))
            rolled_away_after_release = bool(final_result.get("rolled_away_after_release", False))
            settled_in_corral_pass = (
                mission_completed_pass
                and final_inside_retrieval_corral
                and ball_stopped_in_corral
                and not rolled_away_after_release
                and post_visit_revisit_count == 0
            )
            final_settle_distance_m = float(final_result.get("final_settle_distance_m", 0.0) or 0.0)
            max_overshoot_distance_m = max(
                [float(item.get("max_overshoot_distance_m", 0.0) or 0.0) for item in target_results],
                default=0.0,
            )
            settle_time_s = float(final_result.get("settle_time_s", 0.0) or 0.0)
            release_recontact_count = sum(int(item.get("release_recontact_count", 0) or 0) for item in target_results)
            fetch_to_pose_reached = bool(final_result.get("fetch_to_pose_reached", False))
            fetch_to_pose_time_s = float(clean_number(final_result.get("fetch_to_pose_time_s")) or 0.0)
            fetch_to_pose_failure_reason = clean_text(final_result.get("fetch_to_pose_failure_reason"))
            fetch_pose_world = (
                final_result.get("fetch_pose_world", {})
                if isinstance(final_result.get("fetch_pose_world"), dict)
                else {}
            )
            shot_outcome = (
                final_result.get("shot_outcome", {})
                if isinstance(final_result.get("shot_outcome"), dict)
                else {}
            )
            fetch_to_pose_pass = bool(mission_completed_pass and fetch_to_pose_reached)
            final_corral_audit: dict[str, Any] = {}
            final_all_targets_inside_retrieval_corral = False
            final_all_targets_stopped = False
            final_three_ball_corral_pass = False
            retrieved_count = 0
            if self.args.scenario_id == "gather_three_ball_zone":
                if mission_completed_pass:
                    final_corral_snapshot = self._run_final_corral_audit(
                        session_id=session_id,
                        state_history_path=state_history_path,
                    )
                else:
                    final_corral_snapshot = self._final_corral_audit_snapshot(
                        session_id=session_id,
                        previous_poses=None,
                    )
                    final_corral_snapshot["final_all_targets_stopped"] = False
                    final_corral_snapshot["final_three_ball_corral_pass"] = False
                final_corral_audit = (
                    final_corral_snapshot.get("final_corral_audit", {})
                    if isinstance(final_corral_snapshot.get("final_corral_audit"), dict)
                    else {}
                )
                final_all_targets_inside_retrieval_corral = bool(
                    final_corral_snapshot.get("final_all_targets_inside_retrieval_corral", False)
                )
                final_all_targets_stopped = bool(final_corral_snapshot.get("final_all_targets_stopped", False))
                retrieved_count = int(final_corral_snapshot.get("retrieved_count", 0) or 0)
                final_three_ball_corral_pass = (
                    mission_completed_pass
                    and final_all_targets_inside_retrieval_corral
                    and final_all_targets_stopped
                    and post_visit_revisit_count == 0
                )
            final_mission_error = mission_error
            if self.mission_objective == MISSION_OBJECTIVE_FETCH_TO_POSE:
                if mission_completed_pass and not fetch_to_pose_pass and not final_mission_error:
                    final_mission_error = fetch_to_pose_failure_reason or "fetch_to_pose_failed"
            elif self.args.scenario_id == "gather_three_ball_zone":
                if mission_completed_pass and not final_three_ball_corral_pass and not final_mission_error:
                    final_mission_error = "final_corral_audit_failed"
            elif mission_completed_pass and not settled_in_corral_pass and not final_mission_error:
                final_mission_error = "settled_in_corral_failed"
            objective_pass = (
                fetch_to_pose_pass
                if self.mission_objective == MISSION_OBJECTIVE_FETCH_TO_POSE
                else final_three_ball_corral_pass
                if self.args.scenario_id == "gather_three_ball_zone"
                else settled_in_corral_pass
            )
            mission_verdict = {
                "generated_utc": utc_now(),
                "type": "gather_mission",
                "pass": bool(objective_pass),
                "mission_completed_pass": mission_completed_pass,
                "mission_objective": self.mission_objective,
                "scenario_id": self.args.scenario_id,
                "scenario_label": self.args.scenario_label,
                "session_id": session_id,
                "world_file": self.world_file,
                "surface_profile": self.surface_profile,
                "route_order": [item["selected_id"] for item in route_decisions],
                "placed_targets": placed_targets,
                "placed_count": len(placed_targets),
                "total_targets": len(self.targets),
                "capture_loss_count": capture_loss_count,
                "handoff_kind": handoff_kind,
                "zone_edge_correction_count": zone_edge_correction_count,
                "place_controller_reentry_count": place_controller_reentry_count,
                "post_visit_revisit_count": post_visit_revisit_count,
                "settle_exit_reason": settle_exit_reason,
                "settle_no_chase_activated": settle_no_chase_activated,
                "settle_no_chase_exit_reason": settle_no_chase_exit_reason,
                "release_gate_blocked_reason": release_gate_blocked_reason,
                "pre_stage_pose_world": pre_stage_pose_world,
                "pre_stage_pose_reached": pre_stage_pose_reached,
                "pre_stage_time_s": round(pre_stage_time_s, 6),
                "pre_stage_handoff_pass": pre_stage_handoff_pass,
                "approach_side_verdict": approach_side_verdict,
                "staging_pose_reached": staging_pose_reached,
                "entered_goal_side_before_capture": entered_goal_side_before_capture,
                "first_contact_push_alignment_deg": first_contact_push_alignment,
                "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                "stage_time_s": round(stage_time_s, 6),
                "capture_entry_reached": capture_entry_reached,
                "capture_entry_time_s": round(capture_entry_time_s, 6),
                "approach_failure_reason": approach_failure_reason,
                "latest_approach_progress": latest_approach_progress,
                "fresh_attempt_approach": fresh_attempt_approach,
                "stopped_with_ball_captured": stopped_with_ball_captured,
                "release_started_with_capture": release_started_with_capture,
                "stop_capture_state": stop_capture_state,
                "release_capture_state": release_capture_state,
                "clean_retention_pass": clean_retention_pass,
                "final_inside_retrieval_corral": final_inside_retrieval_corral,
                "final_center_inside_zone": final_center_inside_zone,
                "ball_stopped_in_corral": ball_stopped_in_corral,
                "rolled_away_after_release": rolled_away_after_release,
                "settled_in_corral_pass": settled_in_corral_pass,
                "fetch_to_pose_reached": fetch_to_pose_reached,
                "fetch_to_pose_pass": fetch_to_pose_pass,
                "fetch_to_pose_time_s": round(fetch_to_pose_time_s, 6),
                "fetch_to_pose_failure_reason": fetch_to_pose_failure_reason,
                "fetch_pose_world": fetch_pose_world,
                "fetch_delivery_radius_m": round(float(self.fetch_delivery_radius_m), 6),
                "shot_outcome": shot_outcome,
                "final_corral_audit": final_corral_audit,
                "final_all_targets_inside_retrieval_corral": final_all_targets_inside_retrieval_corral,
                "final_all_targets_stopped": final_all_targets_stopped,
                "final_three_ball_corral_pass": final_three_ball_corral_pass,
                "retrieved_count": retrieved_count,
                "final_settle_distance_m": round(final_settle_distance_m, 6),
                "max_overshoot_distance_m": round(max_overshoot_distance_m, 6),
                "settle_time_s": round(settle_time_s, 6),
                "release_recontact_count": release_recontact_count,
                "mission_time_s": mission_time_s,
                "zone_pose": {
                    "x": round(self.zone.world_x, 6),
                    "y": round(self.zone.world_y, 6),
                    "radius_m": round(self.zone.retrieval_radius_m, 6),
                    "control_radius_m": round(self.zone.control_radius_m, 6),
                    "dwell_s": round(self.zone.dwell_s, 6),
                },
                "mission_error": final_mission_error,
                "mission_root": str(mission_root),
            }
            mission_verdict["summary_path"] = str(mission_root / "summary.json")
            write_json(mission_root / "mission_verdict.json", mission_verdict)

            summary = {
                "generated_utc": utc_now(),
                "type": "gather_mission",
                "pass": bool(mission_verdict["pass"]),
                "scenario_id": self.args.scenario_id,
                "scenario_label": self.args.scenario_label,
                "mission_objective": self.mission_objective,
                "session_id": session_id,
                "world_file": self.world_file,
                "surface_profile": self.surface_profile,
                "route_order": mission_verdict["route_order"],
                "placed_targets": placed_targets,
                "placed_count": mission_verdict["placed_count"],
                "mission_completed_pass": mission_completed_pass,
                "capture_loss_count": capture_loss_count,
                "handoff_kind": handoff_kind,
                "zone_edge_correction_count": zone_edge_correction_count,
                "place_controller_reentry_count": place_controller_reentry_count,
                "post_visit_revisit_count": post_visit_revisit_count,
                "settle_exit_reason": settle_exit_reason,
                "settle_no_chase_activated": settle_no_chase_activated,
                "settle_no_chase_exit_reason": settle_no_chase_exit_reason,
                "release_gate_blocked_reason": release_gate_blocked_reason,
                "pre_stage_pose_world": pre_stage_pose_world,
                "pre_stage_pose_reached": pre_stage_pose_reached,
                "pre_stage_time_s": round(pre_stage_time_s, 6),
                "pre_stage_handoff_pass": pre_stage_handoff_pass,
                "approach_side_verdict": approach_side_verdict,
                "staging_pose_reached": staging_pose_reached,
                "entered_goal_side_before_capture": entered_goal_side_before_capture,
                "first_contact_push_alignment_deg": first_contact_push_alignment,
                "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                "stage_time_s": round(stage_time_s, 6),
                "capture_entry_reached": capture_entry_reached,
                "capture_entry_time_s": round(capture_entry_time_s, 6),
                "approach_failure_reason": approach_failure_reason,
                "latest_approach_progress": latest_approach_progress,
                "fresh_attempt_approach": fresh_attempt_approach,
                "stopped_with_ball_captured": stopped_with_ball_captured,
                "release_started_with_capture": release_started_with_capture,
                "stop_capture_state": stop_capture_state,
                "release_capture_state": release_capture_state,
                "clean_retention_pass": clean_retention_pass,
                "final_inside_retrieval_corral": final_inside_retrieval_corral,
                "final_center_inside_zone": final_center_inside_zone,
                "ball_stopped_in_corral": ball_stopped_in_corral,
                "rolled_away_after_release": rolled_away_after_release,
                "settled_in_corral_pass": settled_in_corral_pass,
                "fetch_to_pose_reached": fetch_to_pose_reached,
                "fetch_to_pose_pass": fetch_to_pose_pass,
                "fetch_to_pose_time_s": round(fetch_to_pose_time_s, 6),
                "fetch_to_pose_failure_reason": fetch_to_pose_failure_reason,
                "fetch_pose_world": fetch_pose_world,
                "fetch_delivery_radius_m": round(float(self.fetch_delivery_radius_m), 6),
                "shot_outcome": shot_outcome,
                "final_corral_audit": final_corral_audit,
                "final_all_targets_inside_retrieval_corral": final_all_targets_inside_retrieval_corral,
                "final_all_targets_stopped": final_all_targets_stopped,
                "final_three_ball_corral_pass": final_three_ball_corral_pass,
                "retrieved_count": retrieved_count,
                "final_settle_distance_m": mission_verdict["final_settle_distance_m"],
                "max_overshoot_distance_m": mission_verdict["max_overshoot_distance_m"],
                "settle_time_s": mission_verdict["settle_time_s"],
                "release_recontact_count": mission_verdict["release_recontact_count"],
                "mission_time_s": mission_time_s,
                "mission_verdict_path": str(mission_root / "mission_verdict.json"),
                "target_results_path": str(target_results_path),
                "scorecard_path": str(mission_root / "scorecard.md"),
            }
            write_json(mission_root / "summary.json", summary)
            scorecard_markdown = build_scorecard_markdown(
                scenario_label=self.args.scenario_label,
                summary={
                    "pass_count": 1 if summary["pass"] else 0,
                    "promotion_gate_pass": summary["pass"],
                    "settled_in_corral_pass_count": 1 if settled_in_corral_pass else 0,
                    "settled_in_corral_fail_count": 0 if settled_in_corral_pass else 1,
                    "fetch_to_pose_pass_count": 1 if fetch_to_pose_pass else 0,
                    "fetch_to_pose_fail_count": 0 if fetch_to_pose_pass else 1,
                    "final_inside_retrieval_corral_count": 1 if final_inside_retrieval_corral else 0,
                    "final_center_inside_zone_count": 1 if final_center_inside_zone else 0,
                    "ball_stopped_in_corral_count": 1 if ball_stopped_in_corral else 0,
                    "rolled_away_after_release_count": 1 if rolled_away_after_release else 0,
                    "clean_retention_pass_count": 1 if clean_retention_pass else 0,
                    "clean_retention_fail_count": 0 if clean_retention_pass else 1,
                    "mission_time_avg_s": summary["mission_time_s"],
                    "mission_time_min_s": summary["mission_time_s"],
                    "mission_time_max_s": summary["mission_time_s"],
                    "handoff_kinds": [handoff_kind],
                    "settle_exit_reasons": [settle_exit_reason] if settle_exit_reason else [],
                    "settle_no_chase_activated_count": 1 if settle_no_chase_activated else 0,
                    "settle_no_chase_exit_reasons": [settle_no_chase_exit_reason] if settle_no_chase_exit_reason and settle_no_chase_exit_reason != "none" else [],
                    "release_gate_blocked_reasons": [release_gate_blocked_reason] if release_gate_blocked_reason and release_gate_blocked_reason != "none" else [],
                    "pre_stage_pose_reached_count": 1 if pre_stage_pose_reached else 0,
                    "pre_stage_handoff_pass_count": 1 if pre_stage_handoff_pass else 0,
                    "pre_stage_time_avg_s": round(pre_stage_time_s, 6),
                    "pre_stage_time_max_s": round(pre_stage_time_s, 6),
                    "approach_side_pass_count": 1 if bool(approach_side_verdict.get("pass", False)) else 0,
                    "approach_side_fail_count": 0 if bool(approach_side_verdict.get("pass", False)) else 1,
                    "entered_goal_side_before_capture_count": 1 if entered_goal_side_before_capture else 0,
                    "staging_pose_reached_count": 1 if staging_pose_reached else 0,
                    "capture_entry_reached_count": 1 if capture_entry_reached else 0,
                    "capture_entry_time_avg_s": round(capture_entry_time_s, 6),
                    "first_contact_push_alignment_avg_deg": round(float(first_contact_push_alignment or 0.0), 6),
                    "capture_loss_count_total": capture_loss_count,
                    "stopped_with_ball_captured_count": 1 if stopped_with_ball_captured else 0,
                    "release_started_with_capture_count": 1 if release_started_with_capture else 0,
                    "surface_profiles": [self.surface_profile],
                    "final_settle_distance_avg_m": summary["final_settle_distance_m"],
                    "final_settle_distance_max_m": summary["final_settle_distance_m"],
                    "max_overshoot_distance_max_m": summary["max_overshoot_distance_m"],
                    "settle_time_avg_s": summary["settle_time_s"],
                    "settle_time_max_s": summary["settle_time_s"],
                    "release_recontact_count_total": summary["release_recontact_count"],
                    "zone_edge_correction_count_total": zone_edge_correction_count,
                    "place_controller_reentry_count_total": place_controller_reentry_count,
                    "post_visit_revisit_count_total": post_visit_revisit_count,
                    "final_all_targets_inside_retrieval_corral_count": 1 if final_all_targets_inside_retrieval_corral else 0,
                    "final_all_targets_stopped_count": 1 if final_all_targets_stopped else 0,
                    "final_three_ball_corral_pass_count": 1 if final_three_ball_corral_pass else 0,
                    "final_three_ball_corral_fail_count": 0 if final_three_ball_corral_pass else 1,
                    "retrieved_count_avg": float(retrieved_count),
                    "retrieved_count_max": retrieved_count,
                },
                runs=[
                    {
                        "run_index": 1,
                        "pass": summary["pass"],
                        "surface_profile": self.surface_profile,
                        "handoff_kind": handoff_kind,
                        "settle_exit_reason": settle_exit_reason,
                        "settle_no_chase_activated": settle_no_chase_activated,
                        "settle_no_chase_exit_reason": settle_no_chase_exit_reason,
                        "release_gate_blocked_reason": release_gate_blocked_reason,
                        "pre_stage_pose_world": pre_stage_pose_world,
                        "pre_stage_pose_reached": pre_stage_pose_reached,
                        "pre_stage_time_s": round(pre_stage_time_s, 6),
                        "pre_stage_handoff_pass": pre_stage_handoff_pass,
                        "approach_side_verdict": approach_side_verdict,
                        "staging_pose_reached": staging_pose_reached,
                        "entered_goal_side_before_capture": entered_goal_side_before_capture,
                        "first_contact_push_alignment_deg": first_contact_push_alignment,
                        "push_direction_yaw_deg": round(push_direction_yaw_deg, 6),
                        "stage_time_s": round(stage_time_s, 6),
                        "capture_entry_reached": capture_entry_reached,
                        "capture_entry_time_s": round(capture_entry_time_s, 6),
                        "approach_failure_reason": approach_failure_reason,
                        "latest_approach_progress": latest_approach_progress,
                        "fresh_attempt_approach": fresh_attempt_approach,
                        "placed_count": summary["placed_count"],
                        "capture_loss_count": capture_loss_count,
                        "zone_edge_correction_count": zone_edge_correction_count,
                        "place_controller_reentry_count": place_controller_reentry_count,
                        "post_visit_revisit_count": post_visit_revisit_count,
                        "stopped_with_ball_captured": stopped_with_ball_captured,
                        "release_started_with_capture": release_started_with_capture,
                        "clean_retention_pass": clean_retention_pass,
                        "final_inside_retrieval_corral": final_inside_retrieval_corral,
                        "final_center_inside_zone": final_center_inside_zone,
                        "ball_stopped_in_corral": ball_stopped_in_corral,
                        "rolled_away_after_release": rolled_away_after_release,
                        "settled_in_corral_pass": settled_in_corral_pass,
                        "final_corral_audit": final_corral_audit,
                        "final_all_targets_inside_retrieval_corral": final_all_targets_inside_retrieval_corral,
                        "final_all_targets_stopped": final_all_targets_stopped,
                        "final_three_ball_corral_pass": final_three_ball_corral_pass,
                        "retrieved_count": retrieved_count,
                        "final_settle_distance_m": summary["final_settle_distance_m"],
                        "max_overshoot_distance_m": summary["max_overshoot_distance_m"],
                        "settle_time_s": summary["settle_time_s"],
                        "release_recontact_count": summary["release_recontact_count"],
                        "mission_time_s": summary["mission_time_s"],
                    }
                ],
            )
            (mission_root / "scorecard.md").write_text(scorecard_markdown, encoding="utf-8")
            self._update_visit_runtime_state(
                running=False,
                proof_state="completed" if mission_verdict["pass"] else "failed",
                mission_verdict=mission_verdict,
                mission_phase="completed" if mission_verdict["pass"] else "failed",
                mission_status="completed" if mission_verdict["pass"] else "failed",
                current_target_id="",
                latest_feedback="Gather mission completed." if mission_verdict["pass"] else f"Gather mission failed: {final_mission_error or 'mission_failed'}.",
                surface_profile=self.surface_profile,
            )
            self._update_gather_runtime_state(
                running=False,
                mission_verdict=mission_verdict,
                mission_phase="completed" if mission_verdict["pass"] else "failed",
                mission_status="completed" if mission_verdict["pass"] else "failed",
                gather_phase="completed" if mission_verdict["pass"] else "failed",
                current_target_id="",
                latest_feedback="Gather mission completed." if mission_verdict["pass"] else f"Gather mission failed: {final_mission_error or 'mission_failed'}.",
                surface_profile=self.surface_profile,
                final_corral_audit=final_corral_audit,
            )
            return summary
        finally:
            self._set_manual_drive(False, mode="shutdown", rationale="Mission cleanup.")
            try:
                current_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
                compose_project = clean_text(current_state.get("compose_project"))
                if compose_project:
                    self._stop_motion_bridge(compose_project)
                if bool(getattr(self.args, "cleanup_mission_models", False)):
                    self._clear_mission_models(current_state)
            except Exception:
                pass
            if self._started_here and not self.args.keep_environment:
                try:
                    self._stop_environment()
                except Exception:
                    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic gather mission through the dashboard control plane.")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--provider", default=os.environ.get("CHASECAR_LLM_PROVIDER", "openai"))
    parser.add_argument("--model", default=os.environ.get("OPENAI_SUPERVISOR_MODEL") or DEFAULT_OPENAI_MODEL)
    parser.add_argument("--reasoning-effort", default=os.environ.get("OPENAI_SUPERVISOR_REASONING_EFFORT") or os.environ.get("OPENAI_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT)
    parser.add_argument("--scenario-id", default="corral_single_ball_place")
    parser.add_argument("--scenario-label", default="Corral Single Ball Place")
    parser.add_argument("--mission-objective", choices=ALLOWED_MISSION_OBJECTIVES, default=os.environ.get("CHASECAR_MISSION_OBJECTIVE", MISSION_OBJECTIVE_GATHER_HERE))
    parser.add_argument("--fetch-target-x", type=optional_float_arg, default=optional_float_arg(os.environ.get("CHASECAR_FETCH_TARGET_X", "")))
    parser.add_argument("--fetch-target-y", type=optional_float_arg, default=optional_float_arg(os.environ.get("CHASECAR_FETCH_TARGET_Y", "")))
    parser.add_argument("--fetch-target-z", type=optional_float_arg, default=optional_float_arg(os.environ.get("CHASECAR_FETCH_TARGET_Z", "")))
    parser.add_argument("--fetch-delivery-radius-m", type=optional_float_arg, default=optional_float_arg(os.environ.get("CHASECAR_FETCH_DELIVERY_RADIUS_M", DEFAULT_FETCH_DELIVERY_RADIUS_M)))
    parser.add_argument("--world-file", default=os.environ.get("WORLD_FILE", ""))
    parser.add_argument("--surface-profile", default=os.environ.get("CHASECAR_SURFACE_PROFILE", "baseline"))
    parser.add_argument("--artifact-kind", default="gather_mission")
    parser.add_argument("--poll-s", type=float, default=0.5)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--environment-timeout-s", type=float, default=360.0)
    parser.add_argument("--visit-timeout-s", type=float, default=120.0)
    parser.add_argument("--capture-timeout-s", type=float, default=20.0)
    parser.add_argument("--place-timeout-s", type=float, default=35.0)
    parser.add_argument("--pursuit-settle-timeout-s", type=float, default=8.0)
    parser.add_argument("--max-retries-per-target", type=int, default=2)
    parser.add_argument("--gather-control-family", choices=ALLOWED_GATHER_CONTROL_FAMILIES, default="baseline")
    parser.add_argument("--max-place-loss-revisits", type=int, default=1)
    parser.add_argument("--target-model-name", default=DEFAULT_TARGET_MODEL_NAME)
    parser.add_argument("--target-model-sdf", default=str(DEFAULT_TARGET_MODEL_SDF))
    parser.add_argument("--zone-model-name", default=DEFAULT_ZONE_MODEL_NAME)
    parser.add_argument("--zone-model-sdf", default=str(DEFAULT_ZONE_MODEL_SDF))
    parser.add_argument("--visit-runtime-json", default=str(DEFAULT_VISIT_RUNTIME_STATE_PATH))
    parser.add_argument("--gather-runtime-json", default=str(DEFAULT_GATHER_RUNTIME_STATE_PATH))
    parser.add_argument("--target-layout-json", default="")
    parser.add_argument("--motion-loop-hz", type=float, default=10.0)
    parser.add_argument("--keep-environment", action="store_true")
    parser.add_argument("--cleanup-mission-models", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = GatherMissionRunner(args)
    summary = runner.run()
    print(f"GATHER_MISSION_SUMMARY={summary['mission_verdict_path']}")
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
