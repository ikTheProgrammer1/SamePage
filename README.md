# SamePage — Couples Alignment Assistant

SamePage helps couples get on the same page after a conversation by comparing each partner’s takeaways, surfacing consensus/divergence, and suggesting reconciliations.

## Quick Start

- Local: `uvicorn main:app --reload`
- Cloud Run: use `cloudbuild.yaml` to build/push/deploy

Env vars:
- `PROJECT_ID` (or `GOOGLE_CLOUD_PROJECT`)
- `REGION` default `us-east1`
- `ENABLE_VERTEX=1` to use Vertex embeddings and Gemini; otherwise deterministic fallbacks

## Architecture

- FastAPI + Jinja2 (single Cloud Run service)
- Firestore: `sessions/{session}`, `sessions/{session}/submissions/A|B`
- Vertex AI: `text-embedding-004` for similarity; Gemini 1.5 Pro for borderline explanations

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

The code includes a clear separation of concerns for a Scorer (hybrid similarity) and a Mediator (LLM explanation). You can wire Google’s Agent Development Kit (ADK) to orchestrate these as two agents. For judging, reference `main.py` and `scoring.py` and enable `ENABLE_VERTEX=1`.
