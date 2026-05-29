# LLM Research Notes

## Purpose

This note captures external implementation patterns that are useful for the current Chasecar LLM integration work.

It is intentionally scoped as design context, not as a long-term roadmap commitment.

For the current in-repo layered control design, see [LLM_CONTROL_ARCHITECTURE.md](./LLM_CONTROL_ARCHITECTURE.md).

## Patterns We Are Borrowing From

### 1. Bounded skill selection

Representative example:

- SayCan: https://say-can.github.io/
- Paper: https://arxiv.org/abs/2204.01691

Why it matters here:

- the model selects from a fixed action set instead of inventing actions
- a separate non-LLM layer checks what is actually feasible
- this maps closely to our frozen intent contract plus preview/readiness gating

Current Chasecar mapping:

- frozen intents in [llm_control_contract.yaml](../runtime/contracts/llm_control_contract.yaml)
- deterministic preview/validation in [dashboard_service.py](../scripts/dashboard_service.py)
- canonical action-space enforcement in [llm_supervisor_core.py](../scripts/llm_supervisor_core.py)

### 2. Closed-loop reasoning over environment feedback

Representative examples:

- Inner Monologue: https://arxiv.org/abs/2207.05608
- ReAct: https://arxiv.org/abs/2210.03629

Why it matters here:

- the model should not plan an entire mission up front
- it should observe state, choose one bounded next action, then re-evaluate
- this matches our shadow supervisor loop much better than a long prompt with multi-step prose

Current Chasecar mapping:

- poll dashboard state
- build a compact digest
- request one bounded decision
- validate it
- remain shadow-only or dispatch only through the authoritative control plane

### 3. Structured tool calling instead of freeform action text

Representative guidance:

- OpenAI Tools guide: https://developers.openai.com/api/docs/guides/tools/
- OpenAI Structured Outputs guide: https://developers.openai.com/api/docs/guides/structured-outputs/

Why it matters here:

- robot actions need machine-checkable output
- function/tool calling is a better fit than freeform JSON when the model is choosing application actions
- strict schemas reduce ambiguity and support safer fail-closed handling

Current Chasecar mapping:

- Responses API provider with strict function schema in [llm_provider_openai.py](../scripts/llm_provider_openai.py)
- deterministic contract and canonical-arg validation in [llm_supervisor_core.py](../scripts/llm_supervisor_core.py)

## Patterns We Are Not Adopting Yet

### 1. End-to-end vision-language-action policies as low-level control

Representative examples:

- PaLM-E: https://arxiv.org/abs/2303.03378
- RT-2: https://arxiv.org/abs/2307.15818

Why not now:

- they imply a different architecture, training story, and deployment burden
- they are not a good match for high-frequency contact control on a calibrated
  golf ball
- the Nav2 corridor-push hypothesis is now evidence-only after the saved
  `right05` stop-short promotion failure; a hybrid stage supervisor is the next
  lane, not raw end-to-end learned `/cmd_vel`

Current calibrated-fetch mapping:

- LM/VLA-style models may supervise task mode, failure interpretation, and
  known maneuver selection through deterministic contracts
- `nav2_followpath_corridor_push_v1` showed Nav2 can own useful real-time
  corridor tracking while a monitor only cancels on success, ball escape, stale
  state, unsafe drift, timeout, or action abort, but it did not promote as the
  sole contact controller
- a smaller local learned model should now predict stage handoffs and bounded
  maneuver classes after simulation training and shadow scoring, using the Nav2
  stop-short artifact as one of the first evaluation cases
- deterministic guards still own command limits, target freshness, ball drift,
  retry budget, and safe stop
- V-JEPA-style world models are relevant as an offboard teacher/research pattern
  for scoring candidate actions against predicted physical outcomes, but full
  video world models are not the Jetbot/Orin onboard control target

### 2. Code-generation-as-policy

Representative example:

- Code as Policies: https://arxiv.org/abs/2209.07753

Why not now:

- it expands the action surface too early
- it is harder to validate and promote safely for operator-facing UAT
- the current system benefits more from a bounded classifier-style action picker

## Current Design Conclusion

The most relevant near-term pattern family for Chasecar is:

1. bounded action selection
2. closed-loop re-evaluation over live state
3. strict tool/function calling
4. deterministic non-LLM gating and fail-closed behavior
5. local learned handoff/proposal in shadow mode before live execution

That is a stronger fit for our current stack than either:

- open-ended agentic planning
- end-to-end VLA low-level control
- generated policy code

## What This Means For Current Work

Near-term implementation should continue to optimize for:

- compact fixed-shape state digests
- one-step decisions instead of multi-step plans
- strict tool schemas
- preview and readiness checks outside the model
- calibrated simulation data for local handoff/proposer training
- offboard world-model teacher labels only when they can be distilled into the
  same bounded action set
- shadow-mode scoring before learned proposals execute
- headless proof before browser UAT promotion

That keeps the path compatible with both:

- remote inference over Wi-Fi
- a smaller local model later, provided it can classify the same digest into the same bounded action set
