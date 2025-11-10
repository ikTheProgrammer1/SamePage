import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    from google.cloud import firestore  # type: ignore
except Exception:  # pragma: no cover - allows local runs without GCP libs installed
    firestore = None  # type: ignore

from scoring import (
    compute_alignment,
    needs_llm_mediator,
    llm_explain_or_fallback,
)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None else default


PROJECT_ID = _env("PROJECT_ID", _env("GOOGLE_CLOUD_PROJECT"))
REGION = _env("REGION", "us-east1")
ENABLE_ADK = _env("ENABLE_ADK", "0") == "1"


def _firestore_client():
    if firestore is None:
        raise RuntimeError("google-cloud-firestore not installed")
    return firestore.Client(project=PROJECT_ID)  # ADC in Cloud Run


def _new_id(prefix: str = "s") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


app = FastAPI(title="SamePage")

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # Auto-create a session on landing for a snappy demo flow
    session_id, token_a, token_b = create_session()
    a_link = request.url_for("partner_form", session=session_id, token=token_a)
    b_link = request.url_for("partner_form", session=session_id, token=token_b)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "session_id": session_id,
            "a_link": str(a_link),
            "b_link": str(b_link),
        },
    )


@app.post("/create")
def create():
    session_id, token_a, token_b = create_session()
    return {"sessionId": session_id, "tokenA": token_a, "tokenB": token_b}


def create_session():
    if firestore is None:
        # Local fallback: pretend session only in-memory (demo/dev)
        session_id = _new_id()
        token_a = _new_id("A")
        token_b = _new_id("B")
        return session_id, token_a, token_b

    client = _firestore_client()
    session_id = _new_id()
    token_a = _new_id("A")
    token_b = _new_id("B")
    now = _now()
    doc_ref = client.collection("sessions").document(session_id)
    doc_ref.set(
        {
            "created_at": now,
            "expires_at": now + timedelta(hours=24),
            "tokenA": token_a,
            "tokenB": token_b,
            "status": "pending",
        }
    )
    return session_id, token_a, token_b


@app.get("/s/{session}/{token}", response_class=HTMLResponse)
def partner_form(request: Request, session: str, token: str):
    who = identify_partner(session, token)
    if who is None:
        raise HTTPException(status_code=404, detail="Invalid session/token")
    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "session": session,
            "token": token,
            "who": who,
        },
    )


def identify_partner(session: str, token: str) -> Optional[str]:
    if firestore is None:
        # Without persistence, derive from token prefix only
        return "A" if token.startswith("A_") else ("B" if token.startswith("B_") else None)
    client = _firestore_client()
    doc = client.collection("sessions").document(session).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    if token == data.get("tokenA"):
        return "A"
    if token == data.get("tokenB"):
        return "B"
    return None


@app.post("/submit")
def submit(
    request: Request,
    session: str = Form(...),
    token: str = Form(...),
    takeaway: str = Form(...),
    req_text: str = Form(...),
    tone: str = Form(...),
    nickname: Optional[str] = Form(None),
    consent: Optional[str] = Form(None),
):
    who = identify_partner(session, token)
    if who is None:
        raise HTTPException(status_code=400, detail="Invalid session/token")
    if consent != "on":
        raise HTTPException(status_code=400, detail="Consent required")

    if firestore is None:
        # No-op for local dev; pretend second partner instantly submits to demo
        # Redirect to result page with a demo computation
        return RedirectResponse(url=f"/result/{session}", status_code=303)

    client = _firestore_client()

    # Save submission
    sub_ref = (
        client.collection("sessions").document(session).collection("submissions").document(who)
    )
    sub_ref.set(
        {
            "takeaway": takeaway.strip(),
            "request": req_text.strip(),
            "tone": tone.strip(),
            "submitted_at": _now(),
            "nickname": (nickname or "").strip() or None,
        }
    )

    # Check if both present
    subs = (
        client.collection("sessions").document(session).collection("submissions").stream()
    )
    subs_dict: Dict[str, Dict[str, Any]] = {}
    for s in subs:
        subs_dict[s.id] = s.to_dict() or {}

    if "A" in subs_dict and "B" in subs_dict:
        # Compute score & possibly LLM explain
        result = compute_alignment(subs_dict["A"], subs_dict["B"])  # type: ignore[arg-type]
        if needs_llm_mediator(result):
            llm = llm_explain_or_fallback(subs_dict["A"], subs_dict["B"], result)
            result.update(llm)

        # Save to session
        client.collection("sessions").document(session).set(
            {"status": "completed", **result}, merge=True
        )
        return RedirectResponse(url=f"/result/{session}", status_code=303)

    return templates.TemplateResponse(
        "waiting.html",
        {
            "request": request,
            "session": session,
        },
    )


@app.get("/result/{session}", response_class=HTMLResponse)
def result(request: Request, session: str):
    if firestore is None:
        # Demo placeholder result when offline
        demo = {
            "score": 72,
            "label": "Partial",
            "consensus": [
                "Both agree on dish ownership tonight",
            ],
            "divergence": [
                "Deadline for trash differs (8am vs afternoon)",
                "Tone mismatch (relieved vs stressed)",
            ],
            "themes": ["chores", "household load"],
            "recommendations": [
                "Pick a specific trash time you both accept",
                "Acknowledge stress and plan a follow-up",
            ],
        }
        return templates.TemplateResponse(
            "result.html", {"request": request, "session": session, **demo}
        )

    client = _firestore_client()
    doc = client.collection("sessions").document(session).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session not found")
    data = doc.to_dict() or {}
    return templates.TemplateResponse(
        "result.html",
        {"request": request, "session": session, **data},
    )


# Optional: expose health endpoint for Cloud Run
@app.get("/healthz")
def healthz():
    return {"ok": True, "ts": int(time.time())}


# Keep an entrypoint for local runs
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=True)
