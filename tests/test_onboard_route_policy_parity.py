import json
import sys
from pathlib import Path

import onboard_route_policy as onboard_policy


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import fetch_planner_handoff_gate as source_policy  # noqa: E402


def _scene_corpus():
    scenes = []
    scenes.extend(
        source_policy.generate_random_scenes(
            seed=20260703,
            random_cases=300,
            scene_set=source_policy.DEFAULT_SCENE_SET,
        )
    )
    scenes.extend(
        source_policy.generate_random_scenes(
            seed=20260704,
            random_cases=100,
            scene_set=source_policy.HARD_SCENE_SET,
        )
    )
    scenes.extend(
        source_policy.generate_random_scenes(
            seed=20260705,
            random_cases=100,
            scene_set=source_policy.OPPOSITE_BEHIND_SCENE_SET,
        )
    )
    scenes.extend(
        source_policy.generate_random_scenes(
            seed=20260706,
            random_cases=100,
            scene_set=source_policy.BROAD_SPATIAL_SCENE_SET,
        )
    )
    assert len(scenes) >= 500
    return scenes


def test_onboard_route_policy_matches_sim_source_for_seeded_scene_corpus():
    for index, scene in enumerate(_scene_corpus()):
        source_label = source_policy.deterministic_route_label(scene)
        onboard_label = onboard_policy.deterministic_route_label(scene)
        assert onboard_label == source_label, json.dumps(
            {"index": index, "scene": scene, "source_label": source_label, "onboard_label": onboard_label},
            indent=2,
            sort_keys=True,
        )

        source_plan = source_policy.compile_maneuver_plan(scene, source_label)
        onboard_plan = onboard_policy.compile_maneuver_plan(scene, onboard_label)
        assert onboard_plan == source_plan, json.dumps(
            {
                "index": index,
                "scene": scene,
                "source_label": source_label,
                "onboard_label": onboard_label,
                "source_plan": source_plan,
                "onboard_plan": onboard_plan,
            },
            indent=2,
            sort_keys=True,
        )
