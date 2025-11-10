# SamePage — ADK Agents Plan

This document specifies the Agent Development Kit (ADK) integration for SamePage, aligning with the ADK documentation in `ADK-documentation.md` and the product plan in `plan.md`.

## Goals
- Model the app’s two roles as agents: Scorer and Mediator.
- Use ADK’s code‑first, modular structure so agents are discoverable by ADK tools (CLI/UI) and callable from the FastAPI service.
- Persist a concise `adk_meta` trace in Firestore for transparency and judging.

## Canonical Structure (ADK‑compliant)
Create agents under `src/` using the discovery pattern described by ADK:

```
src/samepage_app/agents/
  scorer/
    __init__.py      # must contain: from . import agent
    agent.py         # must define: root_agent = Agent(...)
  mediator/
    __init__.py
    agent.py         # root_agent = Agent(...)
```

Notes
- Each `agent.py` exposes a top‑level `root_agent` symbol.
- `__init__.py` must contain `from . import agent` so ADK can discover the agent.
- You can optionally add a coordinator agent (e.g., `samepage/agent.py`) to compose sub‑agents, but for MVP two stand‑alone agents are sufficient.

## Agent Specifications

### Scorer Agent
- Purpose: Compute 0–100 alignment score and structured findings.
- Inputs: Partner A and B fields: `takeaway`, `request`, `tone`.
- Tools: One custom FunctionTool wrapping our deterministic scorer.
- Output: `{score, label, consensus[], divergence[], themes[], _evidence}`

Example (agent.py):
```python
from typing import Any, Dict
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from scoring import compute_alignment

def _score_alignment(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    return compute_alignment(a, b)

score_alignment = FunctionTool(_score_alignment)

root_agent = Agent(
    name="scorer",
    model="gemini-2.5-flash",
    instruction=(
        "Compute a 0–100 alignment score and return a compact JSON with "
        "score, label, consensus, divergence, themes, and evidence."
    ),
    description="SamePage Scorer agent",
    tools=[score_alignment],
)
```

### Mediator Agent
- Purpose: For borderline scores, generate short explanation and 2–3 reconciliation rephrasings.
- Inputs: Partner A, B, and `base_result` from Scorer.
- Tools: One custom FunctionTool that calls Gemini (or deterministic fallback).
- Output: `{llm_explainer, recommendations[], llm_latency_ms}`

Example (agent.py):
```python
from typing import Any, Dict
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from scoring import needs_llm_mediator, llm_explain_or_fallback

def _mediate(a: Dict[str, Any], b: Dict[str, Any], base_result: Dict[str, Any]) -> Dict[str, Any]:
    if not needs_llm_mediator(base_result):
        return {"llm_explainer": None, "recommendations": [], "llm_latency_ms": None}
    return llm_explain_or_fallback(a, b, base_result)

mediate = FunctionTool(_mediate)

root_agent = Agent(
    name="mediator",
    model="gemini-2.5-pro",
    instruction=(
        "You are a neutral mediator. For borderline scores, provide a 3–4 sentence explanation "
        "and 2–3 short reconciliation rephrasings."
    ),
    description="SamePage Mediator agent",
    tools=[mediate],
)
```

## Orchestration

### In‑App (FastAPI)
- When both submissions exist:
  1) Invoke Scorer to compute `base_result`.
  2) If `60 ≤ score ≤ 75`, invoke Mediator to enrich with `llm_explainer`, `recommendations`, and `llm_latency_ms`.
  3) Write combined result to `sessions/{session}` and optionally include `adk_meta` for transparency.
- Enable via env flag: `ENABLE_ADK=1`. When off, the app calls the same deterministic functions directly without ADK.

Pseudocode
```python
if ENABLE_ADK:
    # Prefer calling the ADK runner/agents to produce outputs
    result = scorer_tool(a, b)
    if needs_llm_mediator(result):
        result.update(mediator_tool(a, b, result))
    save({**result, "adk_meta": {...}})
else:
    # Deterministic path (no ADK)
    result = compute_alignment(a, b)
    if needs_llm_mediator(result):
        result.update(llm_explain_or_fallback(a, b, result))
    save(result)
```

### Local Dev (ADK CLI/UI)
- Inspect agents via ADK tools:
  - Debug UI: `adk web src/samepage_app/agents/scorer`
  - CLI run: `adk run src/samepage_app/agents/mediator`
  - Serve as API (optional): `adk api_server src/samepage_app/agents/scorer`

## Firestore Data Contract
- `sessions/{session}` includes ADK trace when `ENABLE_ADK=1`:
  - `adk_meta.adk_used: bool`
  - `adk_meta.scorer.output: {score,label,consensus[],divergence[],themes[]}`
  - `adk_meta.mediator.output: {llm_explainer,recommendations[],llm_latency_ms}` or `adk_meta.mediator.skipped: true`
- Submissions remain at `sessions/{session}/submissions/A|B` with the same schema.

## Deployment
- Cloud Run service env:
  - `PROJECT_ID`, `REGION` (set in `cloudbuild.yaml`)
  - `ENABLE_VERTEX=1` to use Vertex embeddings/Gemini
  - `ENABLE_ADK=1` to exercise ADK agents
- IAM for runtime service account:
  - `roles/datastore.user` (Firestore)
  - `roles/aiplatform.user` (Vertex AI)
  - `roles/artifactregistry.reader` (image pulls)

## Verification Checklist
- Open app, complete a session, and confirm in Firestore that:
  - `sessions/{session}.adk_meta.adk_used` is true when ADK is available
  - Scorer output fields are populated; Mediator populated only in 60–75 band
- ADK CLI works:
  - `adk web src/samepage_app/agents/scorer` opens the inspector
  - `adk run src/samepage_app/agents/mediator` returns a JSON payload for test inputs

## Optional Enhancements
- Add a small “Agents: ADK” badge on the result page when `adk_meta` exists.
- Introduce a `ToolLoggerPlugin` (see `ADK-documentation.md`) in an `App` wrapper for richer traces.
- Add evaluation tests using the ADK Evaluation Framework.

## Notes
- ADK Python imports follow the `google.adk` module path (e.g., `from google.adk.agents import Agent`, `from google.adk.tools import FunctionTool`). Ensure imports in integration code reflect this namespace.
- The deterministic scorer/mediator logic lives in `scoring.py` to keep behavior stable regardless of ADK availability.
