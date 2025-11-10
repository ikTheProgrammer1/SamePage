from typing import Any, Dict

from google.adk.agents import Agent  # type: ignore
from google.adk.tools import FunctionTool  # type: ignore

from scoring import compute_alignment


def _score_alignment(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute alignment score and structured findings.
    Args:
      a: {takeaway, request, tone}
      b: {takeaway, request, tone}
    Returns:
      Dict with {score, label, consensus[], divergence[], themes[], _evidence}
    """
    return compute_alignment(a, b)


score_alignment = FunctionTool(_score_alignment)

root_agent = Agent(
    name="scorer",
    model="gemini-2.5-flash",
    instruction=(
        "You compute a 0–100 alignment score between two partners' inputs and return "
        "a compact JSON with score, label, consensus, divergence, and themes."
    ),
    description="SamePage Scorer agent",
    tools=[score_alignment],
)

