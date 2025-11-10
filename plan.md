# SamePage — Couples Alignment Assistant (Cloud Run Hackathon)

## 1) One-liner

AI that helps couples **get on the same page** after a conversation by comparing each partner’s takeaways, surfacing consensus/divergence, and suggesting reconciliations.

## 2) Problem

Most arguments persist because partners **misunderstand** each other — they leave talks with different mental models without realizing it.

## 3) Solution (MVP)

Each partner types three brief fields. We compute a **0–100 Alignment Score** with a label (Aligned / Partial / Misaligned), then show **consensus**, **divergence**, **themes**, and **recommendations**. If the score is borderline, Gemini adds a concise explanation.

### Inputs (per partner)

* **Key takeaway** (1–2 sentences)
* **Request / Next step** (who/what/when)
* **Tone** (one word)

### Output card (ordered)

1. Alignment score + label
2. One-line summary (where aligned vs not)
3. Consensus (≤3 bullets)
4. Divergences (≤3 bullets)
5. Key themes (tags)
6. Recommendations (2–3 rephrasings)

## 4) Scoring (Hybrid + Gemini tie-breaker)

* **Weights (sum 100):** Takeaway **50**; Request **30** *(actor 15 / action 10 / due 5)*; Tone **20**
* **Computation:** per-field similarity (0–1) × weight → sum **0–100**
* **Labels:** 85–100 **Aligned**; 65–84 **Partial**; 0–64 **Misaligned**
* **Gemini band:** trigger explainer at **60–75** (temp=0, JSON-mode)

## 5) Demo Scenario (Chores / Household Load)

**Partner A**

* Takeaway: “We agreed I’ll handle dishes tonight and you’ll take trash tomorrow.”
* Next step: “I’ll do dishes after dinner today; you take trash out by 8am tomorrow.”
* Tone: “relieved”

**Partner B**

* Takeaway: “We decided to rotate chores this week: I’ll do dishes tonight; you do trash tomorrow.”
* Next step: “I’ll do dishes tonight; you take trash out sometime tomorrow afternoon.”
* Tone: “still a bit stressed”

**Expected:** **Partial** — dish owner aligns; trash **deadline** + **tone** diverge.

## 6) Architecture (Cloud Run)

* **Service A (FastAPI + Jinja2):** serves forms & result page; computes hybrid score; calls Gemini if 60–75
* **Firestore:** sessions, tokens, submissions, scores, TTL
* **Vertex AI:** `text-embedding-004` for similarity
* **Gemini 1.5 Pro:** JSON explanation/tie-breaker (sync call)
* **Region:** `us-east1`

### Routes

* `GET /` → landing (create session; show two shareable links)
* `POST /create` → issue `{sessionId, tokenA, tokenB}`
* `GET /s/{session}/{token}` → partner form (A or B)
* `POST /submit` → save; if both present → score → (maybe Gemini) → redirect
* `GET /result/{session}` → alignment card

### Firestore Schema

* `sessions/{sessionId}`:
  `created_at, expires_at, nickname_a, nickname_b, status, score, label, consensus[], divergence[], themes[], recommendations[], needs_llm, llm_explainer, llm_latency_ms`
* `sessions/{sessionId}/submissions/A|B`:
  `takeaway, request, tone, submitted_at, ip_hash`
* `metrics_daily/{YYYY-MM-DD}`:
  `sessions_count, avg_score, pct_aligned, pct_partial, pct_misaligned, top_themes[]`

## 7) Privacy & Data Retention

* **Anonymous by default** (“Partner A/B”), optional nicknames
* **Short-lived:** keep raw sessions **24 hours** via Firestore TTL; retain only anonymized aggregates afterward
* Consent checkbox: “Store this session up to 24 hours to show results; then we delete the text.”

## 8) Tech Stack

* **Backend/UI:** FastAPI + Jinja2 (Tailwind via CDN) — single Cloud Run service
* **State:** Firestore (native IAM)
* **AI:** Vertex embeddings; Gemini explainer (temp=0, JSON schema)
* **Infra:** Dockerfile → Artifact Registry → Cloud Build → Cloud Run

## 9) Submission Assets

* **README:** one-paragraph pitch; architecture diagram (PNG + ASCII)
* **Demo video (~3 min):**

  1. 15s problem hook
  2. 45s partners enter forms
  3. 60s results (score 65–80 Partial) + “why” evidence
  4. 45s apply recommendation → resubmit → score rises
  5. 15s Cloud Run/Vertex/Gemini & autoscale logs
* **Public repo:** Dockerfile, `main.py`, templates, Firestore rules, deploy script
* **Try-it link:** public Cloud Run URL
* **Optional:** AI Studio prompt link; blog/X/LinkedIn post with `#CloudRunHackathon`

## 10) Implementation Steps (2–3 days)

**Day 1**

* Scaffold FastAPI routes & templates; Firestore writes; tokenized two-link flow
* Embed & cosine for Takeaway; simple parser for Request; tone label compare

**Day 2**

* Weighting/thresholds; consensus/divergence/themes (keyword + semantic clustering)
* Gemini JSON explainer for 60–75 band; timeout & fallback
* Result card polish (Tailwind)

**Day 3**

* TTL rules; metrics aggregation; seed demo session; record demo
* README, diagram, deploy scripts, public URL test

## 11) Evaluation Metrics

* Completion with both submissions: **>95%** (demo)
* Avg LLM latency: **<2.5s**
* Distribution: % Aligned / Partial / Misaligned
* Trust signals on card: cosine subscores + actor/action/due evidence

## 12) Risks & Mitigations

* **LLM delay:** timeout + deterministic fallback; spinner text
* **Edge phrasing:** normalize inputs; clip cosine <0 to 0; synonyms list
* **Creepy optics:** anonymous default; 24h TTL; plain-English policy in footer

## 13) ADK Integration (AI Agents Category)

**Why:** The AI Agents track requires using Google’s Agent Development Kit (ADK).

### Agents

* **Scorer**
  *Goal:* compute 0–100 alignment score and structured findings.
  *Tools:* `EmbeddingsTool` (Vertex `text-embedding-004`), `RequestParseTool` (actor/action/due), `ToneCompareTool`.
  *Output:* `{score, label, consensus[], divergence[], themes[]}`

* **Mediator**
  *Goal:* generate short explanation + 2–3 reconciliation rephrasings when score is borderline.
  *Tools:* `GeminiExplainTool` (Gemini 1.5 Pro, JSON-mode, temp=0).
  *Output:* `{llm_explainer, recommendations[], llm_latency_ms}`

### Orchestration (ADK Runner)

Flow: When both submissions exist → **Scorer** runs → if `60 ≤ score ≤ 75` → **Mediator** runs → results saved to Firestore → render `/result/{session}`.

### Cloud Run Deployment

* Single service (FastAPI + Jinja2) invokes the ADK runner synchronously inside `POST /submit`.
* Region: `us-east1`.
* State: Firestore (sessions, submissions, scores) with 24h TTL.

### Proof for Judges

* README section: agent diagram (Scorer → Mediator) and short code excerpt showing `adk.Agent(...)` and `runner.run(...)`.
* Logs screenshot: Scorer output (score + fields) then Mediator output (explanation + recommendations).
* Demo video: quick clip of ADK runner call and results.

---

## Appendix A — Minimal File Tree

```
samepage/
  Dockerfile
  cloudbuild.yaml
  main.py                # FastAPI app + ADK runner calls
  scoring.py             # embeddings, request parse, tone compare, weights
  templates/
    base.html
    form.html
    result.html
  static/
    tailwind.css         # optional (or use CDN)
  firestore_rules/       # optional rules export
  README.md
```

## Appendix B — Result Card Anatomy (data bindings)

* **Score + label** → `sessions.score`, `sessions.label`
* **Summary line** → composed from consensus/divergence counts
* **Consensus bullets** → `sessions.consensus[]`
* **Divergences bullets** → `sessions.divergence[]`
* **Themes** → `sessions.themes[]`
* **Recommendations** → `sessions.recommendations[]` (from Mediator/LLM)
* **Evidence (debug toggle)** → cosine subscores; actor/action/due matches
