from typing import Any, Dict

from google.adk.agents import Agent  # type: ignore
from google.adk.tools import FunctionTool  # type: ignore

from scoring import needs_llm_mediator, llm_explain_or_fallback


def _mediate(a: Dict[str, Any], b: Dict[str, Any], base_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    If the score is borderline, produce an explainer and 2–3 recommendations.
    Args:
      a, b: partner inputs
      base_result: output from scorer (must include 'score')
    Returns:
      Dict with {llm_explainer, recommendations[], llm_latency_ms}
    """
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

