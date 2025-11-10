import math
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# ---- Embeddings (Vertex AI with safe fallback) ----

def _vertex_available() -> bool:
    try:
        import vertexai  # type: ignore
        from vertexai.preview.language_models import TextEmbeddingModel  # noqa: F401

        return True
    except Exception:
        return False


def _vertex_embed(texts: List[str]) -> List[List[float]]:
    import vertexai  # type: ignore
    from vertexai.preview.language_models import TextEmbeddingModel  # type: ignore

    project = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    # Prefer a dedicated Vertex region; default to us-central1
    region = os.getenv("VERTEX_REGION") or os.getenv("REGION") or "us-central1"
    if project:
        vertexai.init(project=project, location=region)  # type: ignore
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    embeddings = model.get_embeddings(texts)
    return [e.values for e in embeddings]


def _bow_embed(texts: List[str]) -> List[List[float]]:
    # Super-simple bag-of-words for offline demos
    vocab: Dict[str, int] = {}
    tokenized: List[List[str]] = []
    for t in texts:
        toks = re.findall(r"[a-zA-Z0-9']+", (t or "").lower())
        tokenized.append(toks)
        for tok in toks:
            if tok not in vocab:
                vocab[tok] = len(vocab)
    out: List[List[float]] = []
    for toks in tokenized:
        vec = [0.0] * len(vocab)
        for tok in toks:
            vec[vocab[tok]] += 1.0
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


def embed_texts(texts: List[str]) -> List[List[float]]:
    use_vertex = os.getenv("ENABLE_VERTEX", "0") == "1"
    if use_vertex and _vertex_available():
        try:
            return _vertex_embed(texts)
        except Exception:
            pass
    return _bow_embed(texts)


def cosine(a: List[float], b: List[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db = math.sqrt(sum(y * y for y in b)) or 1.0
    c = max(0.0, min(1.0, num / (da * db)))
    return c


# ---- Request parsing / tone compare ----

@dataclass
class ParsedRequest:
    actor: Optional[str]
    action: Optional[str]
    due: Optional[str]


_ACTOR_RE = re.compile(r"\b(I|you|we|me|us)\b", re.I)
_DUE_RE = re.compile(
    r"\b(today|tonight|tomorrow|by\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm)|afternoon|morning|evening)\b",
    re.I,
)


def parse_request(text: str) -> ParsedRequest:
    text = (text or "").strip()
    if not text:
        return ParsedRequest(None, None, None)
    actor_match = _ACTOR_RE.search(text)
    due_match = _DUE_RE.search(text)
    # Naive action = text sans actor/due tokens
    action = text
    if actor_match:
        action = action.replace(actor_match.group(0), "").strip()
    if due_match:
        action = action.replace(due_match.group(0), "").strip()
    action = re.sub(r"\s+", " ", action)
    return ParsedRequest(
        actor=actor_match.group(0).lower() if actor_match else None,
        action=action or None,
        due=due_match.group(0).lower() if due_match else None,
    )


_TONE_MAP = {
    "positive": {
        "relieved",
        "calm",
        "content",
        "hopeful",
        "optimistic",
        "happy",
        "excited",
    },
    "negative": {
        "stressed",
        "anxious",
        "frustrated",
        "angry",
        "worried",
        "sad",
        "upset",
    },
    "neutral": {"neutral", "ok", "meh", "fine"},
}


def tone_bucket(tone: str) -> str:
    t = (tone or "").strip().lower()
    if not t:
        return "neutral"
    for k, vs in _TONE_MAP.items():
        if t in vs:
            return k
    return t  # treat unknown as its own bucket


def tone_similarity(a: str, b: str) -> float:
    ba, bb = tone_bucket(a), tone_bucket(b)
    if ba == bb:
        return 1.0
    if "neutral" in (ba, bb):
        return 0.6
    return 0.25


# ---- Scoring ----

WEIGHTS = {
    "takeaway": 50,
    "request_actor": 15,
    "request_action": 10,
    "request_due": 5,
    "tone": 20,
}


def label_for(score: float) -> str:
    if score >= 85:
        return "Aligned"
    if score >= 65:
        return "Partial"
    return "Misaligned"


def compute_alignment(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    take_a, take_b = a.get("takeaway", ""), b.get("takeaway", "")
    req_a, req_b = a.get("request", ""), b.get("request", "")
    tone_a, tone_b = a.get("tone", ""), b.get("tone", "")

    # Takeaway similarity (embedding or fallback)
    v_take = embed_texts([take_a, take_b])
    sim_take = cosine(v_take[0], v_take[1])

    # Request parsing
    pa, pb = parse_request(req_a), parse_request(req_b)
    actor_sim = 1.0 if pa.actor and pb.actor and pa.actor == pb.actor else 0.0
    action_sim = 0.0
    if pa.action and pb.action:
        v_act = embed_texts([pa.action, pb.action])
        action_sim = cosine(v_act[0], v_act[1])
    due_sim = 1.0 if pa.due and pb.due and pa.due == pb.due else 0.0

    # Tone
    tone_sim = tone_similarity(tone_a, tone_b)

    # Weighted score
    score = (
        sim_take * WEIGHTS["takeaway"]
        + actor_sim * WEIGHTS["request_actor"]
        + action_sim * WEIGHTS["request_action"]
        + due_sim * WEIGHTS["request_due"]
        + tone_sim * WEIGHTS["tone"]
    )
    score = max(0.0, min(100.0, score))
    label = label_for(score)

    # Findings
    consensus: List[str] = []
    divergence: List[str] = []
    themes = extract_themes([take_a, take_b, req_a, req_b])

    if sim_take >= 0.75:
        consensus.append("Shared understanding of the main takeaway")
    else:
        divergence.append("Different interpretations of the main takeaway")

    if actor_sim >= 0.99:
        consensus.append("Agreement on who does what")
    else:
        divergence.append("Actor assignment differs")

    if action_sim >= 0.75:
        consensus.append("Similar next-step action")
    else:
        divergence.append("Action details differ")

    if due_sim >= 0.99:
        consensus.append("Same deadline/timeframe")
    else:
        divergence.append("Deadline/timeframe differs")

    if tone_sim >= 0.9:
        consensus.append("Similar emotional tone")
    elif tone_sim <= 0.4:
        divergence.append("Tone mismatch")

    data = {
        "score": round(score, 1),
        "label": label,
        "consensus": consensus[:3],
        "divergence": divergence[:3],
        "themes": themes,
        # Debug/evidence (can be shown behind toggle)
        "_evidence": {
            "takeaway_sim": round(sim_take, 3),
            "actor_sim": actor_sim,
            "action_sim": round(action_sim, 3),
            "due_sim": due_sim,
            "tone_sim": round(tone_sim, 3),
            "parsed_a": pa.__dict__,
            "parsed_b": pb.__dict__,
        },
    }
    return data


def needs_llm_mediator(result: Dict[str, Any]) -> bool:
    score = float(result.get("score", 0))
    return 60.0 <= score <= 75.0


def llm_explain_or_fallback(
    a: Dict[str, Any], b: Dict[str, Any], result: Dict[str, Any]
) -> Dict[str, Any]:
    # Try Gemini via Vertex; fallback if not available
    try:
        from vertexai.generative_models import GenerativeModel  # type: ignore
        import vertexai  # type: ignore

        project = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        # Prefer a dedicated Vertex region; default to us-central1
        region = os.getenv("VERTEX_REGION") or os.getenv("REGION") or "us-central1"
        if project:
            vertexai.init(project=project, location=region)  # type: ignore
        model = GenerativeModel("gemini-2.5-pro")
        prompt = _mediator_prompt(a, b, result)
        resp = model.generate_content(prompt, generation_config={"temperature": 0})
        text = (resp.candidates[0].content.parts[0].text or "").strip()  # type: ignore
        recs = _extract_bullets(text)[:3]
        return {
            "llm_explainer": text,
            "recommendations": recs if recs else _fallback_recs(a, b, result),
            "llm_latency_ms": None,
        }
    except Exception:
        # Deterministic fallback
        return {
            "llm_explainer": _fallback_explainer(a, b, result),
            "recommendations": _fallback_recs(a, b, result),
            "llm_latency_ms": None,
        }


def _mediator_prompt(a: Dict[str, Any], b: Dict[str, Any], result: Dict[str, Any]) -> str:
    return (
        "You are a neutral mediator. Given Partner A and Partner B inputs, "
        "write a concise explanation (3-4 sentences) of where they align and where they differ. "
        "Then provide 2-3 short reconciliation rephrasings they could adopt.\n\n"
        f"A_takeaway: {a.get('takeaway')}\nA_request: {a.get('request')}\nA_tone: {a.get('tone')}\n"
        f"B_takeaway: {b.get('takeaway')}\nB_request: {b.get('request')}\nB_tone: {b.get('tone')}\n\n"
        f"Score: {result.get('score')} Label: {result.get('label')}\n"
        "Output as plain text with a short paragraph followed by bullets."
    )


def _extract_bullets(text: str) -> List[str]:
    lines = [l.strip(" -*•\t") for l in text.splitlines()]
    return [l for l in lines if l]


def _fallback_explainer(a: Dict[str, Any], b: Dict[str, Any], result: Dict[str, Any]) -> str:
    parts = []
    parts.append(
        "You share overlap on the gist, but differ on details like deadline and emotional tone."
    )
    parts.append(
        "Clarifying a specific time and acknowledging each other's feelings can improve alignment."
    )
    return " ".join(parts)


def _fallback_recs(a: Dict[str, Any], b: Dict[str, Any], result: Dict[str, Any]) -> List[str]:
    recs = [
        "Pick a concrete deadline you both accept",
        "Summarize the next step in one sentence you both sign off on",
        "Acknowledge emotions, then confirm the plan verbally",
    ]
    return recs


def extract_themes(texts: List[str]) -> List[str]:
    joined = " ".join(texts).lower()
    themes = []
    for kw, tag in [
        ("dishes", "chores"),
        ("trash", "chores"),
        ("laundry", "chores"),
        ("deadline", "timing"),
        ("tomorrow", "timing"),
        ("tonight", "timing"),
        ("budget", "money"),
        ("money", "money"),
        ("schedule", "time management"),
        ("calendar", "time management"),
        ("weekend", "planning"),
    ]:
        if kw in joined and tag not in themes:
            themes.append(tag)
    if not themes:
        # fallback to top unigrams
        tokens = re.findall(r"[a-zA-Z0-9']+", joined)
        freq: Dict[str, int] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        themes = [w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:3]]
    return themes[:5]
