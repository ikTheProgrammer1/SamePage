import os
import time
from typing import Any, Dict, Tuple
import sys
from pathlib import Path

from scoring import compute_alignment, needs_llm_mediator, llm_explain_or_fallback
from typing import Optional
import traceback


def _adk_available() -> tuple[bool, Optional[str]]:
    """Detect whether ADK is available in this runtime.

    Returns (available, note). We try multiple signals in order:
    1) Module import of `google.adk` (canonical)
    2) Alternate module name `google_adk`
    3) Installed distribution `google-adk` present (namespace may be shadowed)
    """
    try:
        import importlib.util as _util
        import importlib.metadata as _md  # type: ignore

        # 1) Canonical import path
        try:
            if _util.find_spec("google.adk") is not None:
                return True, None
        except Exception:
            pass

        # 2) Alternate module name sometimes used in early builds
        try:
            if _util.find_spec("google_adk") is not None:
                return True, "google_adk module present; google.adk not found"
        except Exception:
            pass

        # 3) Distribution is installed but namespace may be shadowed
        try:
            _md.version("google-adk")
            return True, "google-adk dist installed; google.adk import blocked by namespace"
        except Exception:
            pass

        # Nothing found
        return False, "ADK not importable and dist not found"
    except Exception as e:  # pragma: no cover - debug-only path
        err = f"{e.__class__.__name__}: {e}"
        try:
            tb = traceback.format_exc(limit=1)
            if tb:
                err = f"{err} | {tb.strip()}"
        except Exception:
            pass
        return False, err


def run_adk_flow(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Orchestrates Scorer → (optional) Mediator and returns (result, adk_meta).

    Uses google-adk if available for orchestration metadata; computation reuses
    our deterministic utilities so the app is reliable even without the SDK.
    """

    adk_used, adk_error = _adk_available()
    adk_meta: Dict[str, Any] = {
        "adk_used": adk_used,
        "adk_error": adk_error,
        "scorer": {},
        "mediator": {},
    }

    if adk_used:
        # Best effort: include descriptors for the defined agents in src/
        try:  # pragma: no cover - only for runtime transparency
            src_dir = Path(__file__).parent / "src"
            if src_dir.is_dir() and str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            # Import root_agent instances defined per ADK discovery rules
            from samepage_app.agents.scorer.agent import root_agent as scorer_agent  # type: ignore
            from samepage_app.agents.mediator.agent import root_agent as mediator_agent  # type: ignore

            adk_meta["scorer"]["agent"] = getattr(scorer_agent, "name", None) or repr(scorer_agent)
            adk_meta["mediator"]["agent"] = getattr(mediator_agent, "name", None) or repr(mediator_agent)
        except Exception as e:
            # Fall back to noting ADK import succeeded, but agent introspection failed
            adk_meta["scorer"]["agent"] = "defined"
            adk_meta["mediator"]["agent"] = "defined"
            adk_meta["agent_import_error"] = f"{e.__class__.__name__}: {e}"

    # Run Scorer (deterministic compute)
    result = compute_alignment(a, b)
    adk_meta["scorer"]["output"] = {
        "score": result.get("score"),
        "label": result.get("label"),
        "consensus": result.get("consensus"),
        "divergence": result.get("divergence"),
        "themes": result.get("themes"),
    }

    # Run Mediator if needed
    if needs_llm_mediator(result):
        t0 = time.time()
        llm = llm_explain_or_fallback(a, b, result)
        t1 = time.time()
        result.update(llm)
        result["llm_latency_ms"] = int((t1 - t0) * 1000)
        adk_meta["mediator"]["output"] = {
            "llm_explainer": result.get("llm_explainer"),
            "recommendations": result.get("recommendations"),
            "llm_latency_ms": result.get("llm_latency_ms"),
        }
    else:
        adk_meta["mediator"]["skipped"] = True

    return result, adk_meta
