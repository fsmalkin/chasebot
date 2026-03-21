#!/usr/bin/env python3
"""Replay recorded bounded-demo state history across provider backends."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from brain_state_digest import build_state_digest
from brain_state_digest import state_digest_hash
from llm_provider_local import LocalModelProvider
from llm_provider_local import LocalStubProvider
from llm_provider_openai import OpenAIResponsesProvider
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import load_contract
from llm_supervisor_core import normalize_model_decision
from llm_supervisor_core import read_json
from llm_supervisor_core import read_jsonl
from llm_supervisor_core import utc_now
from llm_supervisor_core import validate_decision_against_canonical_space
from llm_supervisor_core import validate_decision_against_contract
from llm_supervisor_core import write_json


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_provider(provider_name: str, model_name: str, reasoning_effort: str):
    if provider_name == "openai":
        return OpenAIResponsesProvider(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=model_name,
            reasoning_effort=reasoning_effort,
            base_url=os.environ.get("OPENAI_BASE_URL", ""),
            org_id=os.environ.get("OPENAI_ORG_ID", ""),
            project_id=os.environ.get("OPENAI_PROJECT_ID", ""),
        )
    if provider_name == "local_stub":
        return LocalStubProvider(model=model_name or "local-stub")
    if provider_name == "local_model":
        return LocalModelProvider(model=model_name or "local-model")
    raise ValueError(f"Unsupported provider: {provider_name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay recorded demo states across providers.")
    parser.add_argument("--proof-root", required=True, help="Path to a proof/demo artifact root containing state_history.jsonl.")
    parser.add_argument("--contract", default=str(REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"))
    parser.add_argument("--providers", default="openai,local_stub")
    parser.add_argument("--model", default=os.environ.get("OPENAI_SUPERVISOR_MODEL") or "gpt-5-nano")
    parser.add_argument("--reasoning-effort", default=os.environ.get("OPENAI_SUPERVISOR_REASONING_EFFORT") or os.environ.get("OPENAI_REASONING_EFFORT") or "medium")
    parser.add_argument("--task", default="")
    parser.add_argument("--sample-limit", type=int, default=8)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    proof_root = Path(args.proof_root).resolve()
    summary = read_json(proof_root / "summary.json")
    verdict = read_json(proof_root / "proof_verdict.json")
    session_id = str(verdict.get("session_id", "") or summary.get("session_id", ""))
    task_text = str(args.task or summary.get("task_text", "")).strip()
    if not task_text:
        raise SystemExit("A task text is required either from the proof summary or --task.")

    state_history = read_jsonl(proof_root / "state_history.jsonl")
    contract = load_contract(Path(args.contract).resolve())
    unique_digests: list[dict[str, object]] = []
    seen_hashes: set[str] = set()
    for entry in state_history:
        enriched = {
            "control_plane_ready": True,
            "environment_state": entry.get("environment_state", "environment_ready"),
            "scenario_state": "running",
            "session_id": session_id,
            "sim_gate_ready": True,
            "phase": entry.get("phase", ""),
            "target_id": entry.get("target_id", ""),
            "perception": entry.get("perception", {}),
            "belief": entry.get("belief", {}),
            "brain": entry.get("brain", {}),
            "outcome": entry.get("outcome", {}),
            "motion_evidence": bool(entry.get("outcome", {}).get("cmd_vel_recent", False)) if isinstance(entry.get("outcome"), dict) else False,
        }
        digest = build_state_digest(enriched, contract)
        digest_hash = state_digest_hash(digest)
        if digest_hash in seen_hashes:
            continue
        seen_hashes.add(digest_hash)
        unique_digests.append({"state_hash": digest_hash, "digest": digest, "generated_utc": entry.get("generated_utc", "")})
        if len(unique_digests) >= max(args.sample_limit, 1):
            break

    comparison_root = proof_root / "provider_compare" / current_utc_stamp()
    providers = [item.strip() for item in str(args.providers).split(",") if item.strip()]
    provider_summaries: list[dict[str, object]] = []
    for provider_name in providers:
        provider = build_provider(provider_name, args.model, args.reasoning_effort)
        enabled, disabled_reason = provider.is_enabled()
        decisions: list[dict[str, object]] = []
        if enabled:
            for item in unique_digests:
                try:
                    result = provider.recommend(
                        task_text=task_text,
                        digest=dict(item["digest"]),
                        contract=contract,
                        timeout_s=args.timeout_s,
                    )
                    decision = normalize_model_decision(result.decision)
                    decision = validate_decision_against_contract(decision, contract)
                    decision = validate_decision_against_canonical_space(decision)
                    decisions.append(
                        {
                            "state_hash": item["state_hash"],
                            "generated_utc": item["generated_utc"],
                            "status": decision.get("status", ""),
                            "intent": decision.get("intent", ""),
                            "args": decision.get("args", {}),
                        }
                    )
                except Exception as exc:
                    decisions.append(
                        {
                            "state_hash": item["state_hash"],
                            "generated_utc": item["generated_utc"],
                            "status": "error",
                            "intent": "",
                            "args": {},
                            "error": str(exc),
                        }
                    )
        provider_summaries.append(
            {
                "provider": provider_name,
                "model": provider.model_name,
                "enabled": enabled,
                "disabled_reason": disabled_reason,
                "decision_count": len(decisions),
                "decisions": decisions,
            }
        )

    payload = {
        "generated_utc": utc_now(),
        "type": "llm_provider_replay_compare",
        "proof_root": str(proof_root),
        "session_id": session_id,
        "task_text": task_text,
        "sample_count": len(unique_digests),
        "providers": provider_summaries,
    }
    write_json(comparison_root / "comparison_summary.json", payload)
    print(f"LLM_PROVIDER_REPLAY_COMPARE_SUMMARY={comparison_root / 'comparison_summary.json'}")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
