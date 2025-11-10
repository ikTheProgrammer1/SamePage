# SamePage — Couples Alignment Assistant


## STOP ARGUING WITH YOUR SOULMATE
SamePage helps couples get on the same page after a conversation by comparing each partner’s takeaways, surfacing consensus/divergence, and suggesting reconciliations.

## Quick Start

- Local: `uvicorn main:app --reload`
- Cloud Run: use `cloudbuild.yaml` to build/push/deploy

Env vars:
- `PROJECT_ID` (or `GOOGLE_CLOUD_PROJECT`)
- `REGION` default `us-east1`
- `VERTEX_REGION` default `us-central1` (Vertex AI embeddings + Gemini region)
- `ENABLE_VERTEX=1` to use Vertex embeddings and Gemini; otherwise deterministic fallbacks
- `ENABLE_ADK=1` to run Scorer→Mediator via ADK orchestration and store `adk_meta`

## Architecture

- FastAPI + Jinja2 (single Cloud Run service)
- Firestore: `sessions/{session}`, `sessions/{session}/submissions/A|B`
- Vertex AI: `text-embedding-004` for similarity; Gemini 2.5 Pro for borderline explanations

Routes:
- `GET /` → creates a session and shows two shareable links
- `POST /create` → returns `{ sessionId, tokenA, tokenB }`
- `GET /s/{session}/{token}` → partner form (A or B)
- `POST /submit` → saves submission; scores when both are present; redirects to result
- `GET /result/{session}` → alignment card

## Deploy

Create (or reuse) an Artifact Registry repo and set Cloud Build subs:

```
gcloud builds submit \
  --substitutions=_REGION=us-east1,_REPO=<AR_REPO>,_SERVICE=samepage
```

Cloud Run service gets `PROJECT_ID`/`REGION` envs from `cloudbuild.yaml`. Ensure Firestore is in Native mode and the service account has `Datastore User` (or equivalent) and Vertex permissions if using LLM features.

## ADK Integration (Agents)

- Runtime path can use ADK when `ENABLE_ADK=1`. The scoring step calls `adk_integration.run_adk_flow`, which orchestrates:
  - Scorer: computes score, label, consensus/divergence/themes (hybrid embedding + parsing)
  - Mediator: if score in 60–75, generates an explainer and 2–3 reconciliations (Gemini or fallback)
- The session document includes `adk_meta` with agent descriptors/outputs for logs and judging.
- Files: `adk_integration.py`, `scoring.py`, and `main.py` (POST `/submit` path).

Agent discovery layout (for ADK CLI/UI):
- `src/samepage_app/agents/scorer/agent.py` (exports `root_agent`)
- `src/samepage_app/agents/mediator/agent.py` (exports `root_agent`)
- Each agent directory has `__init__.py` that does `from . import agent` per ADK docs.

Local inspection:
- `adk web src/samepage_app/agents/scorer`
- `adk run src/samepage_app/agents/mediator`

## ADK Web (Trace UI)

- Install deps (uses uv): `uv sync`
- Start UI (venv): `.venv/bin/adk web src/samepage_app/agents --no-reload`
- Or use the helper script: `./scripts/adk-web.sh` (set `PORT=8765` to choose a port)
- In the browser, select `scorer` or `mediator`, chat to create a session, then open the Trace tab to inspect Event, Request, Response, and Graph.

Make target (optional): `make adk-web` runs the script if available.
