#!/usr/bin/env python3
"""CLI entrypoint for the headless frozen-intent LLM recommender."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from brain_llm_recommender import (
    DEFAULT_DASHBOARD_URL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REASONING_EFFORT,
    REPO_ROOT,
    run_recommendation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recommend one frozen intent from a task string.")
    parser.add_argument("--task", required=True, help="Operator task text for the LLM planner.")
    parser.add_argument(
        "--dashboard-url",
        default=os.environ.get("CHASECAR_DASHBOARD_URL", DEFAULT_DASHBOARD_URL),
        help="Dashboard base URL used for state, preview, and dispatch.",
    )
    parser.add_argument(
        "--contract",
        default=str(REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"),
        help="Path to the frozen control contract.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        help="OpenAI model name.",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=os.environ.get("OPENAI_REASONING_EFFORT", DEFAULT_REASONING_EFFORT),
        help="OpenAI reasoning effort setting.",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Dispatch automatically after a valid recommendation and preview gate.",
    )
    parser.add_argument(
        "--prompt-approve",
        action="store_true",
        help="Prompt for interactive approval after a valid recommendation and preview gate.",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=45.0,
        help="HTTP timeout for dashboard and OpenAI requests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_recommendation(
        task_text=args.task,
        contract_path=Path(args.contract).resolve(),
        dashboard_url=args.dashboard_url,
        approve=bool(args.approve),
        prompt_approve=bool(args.prompt_approve),
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_base_url=os.environ.get("OPENAI_BASE_URL", ""),
        openai_org_id=os.environ.get("OPENAI_ORG_ID", ""),
        openai_project_id=os.environ.get("OPENAI_PROJECT_ID", ""),
        timeout_s=args.timeout_s,
    )

    summary = result["summary"]
    decision = summary["decision"]
    print(f"LLM_RECOMMENDATION_SUMMARY={result['artifacts']['summary_path']}")
    print(f"LLM_RECOMMENDATION_HISTORY={result['artifacts']['history_path']}")
    print(f"LLM_RECOMMENDATION_STATUS={decision.get('status', '')}")
    print(f"LLM_RECOMMENDATION_INTENT={decision.get('intent', '')}")
    print(f"LLM_RECOMMENDATION_APPROVED={summary.get('approved', False)}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
