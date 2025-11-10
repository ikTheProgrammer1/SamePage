"""
Optional ADK wiring demo for judges.

This file shows how the Scorer and Mediator could be wired using Google ADK.
Not used in the runtime path by default.
"""

from typing import Any, Dict


def example_adk_flow(inputs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # The API may vary by version; adjust as needed.
        from google_adk import Agent, Runner  # type: ignore
    except Exception:
        # Library not installed; return passthrough
        return {"error": "google_adk not installed"}

    # Pseudo-tools; in practice these would call scoring.parse_request, embeddings, etc.
    scorer = Agent(
        name="Scorer",
        tools=["EmbeddingsTool", "RequestParseTool", "ToneCompareTool"],
        goal="Compute 0–100 alignment score and findings",
    )
    mediator = Agent(
        name="Mediator",
        tools=["GeminiExplainTool"],
        goal="Explain divergences and propose reconciliations when score is borderline",
    )

    runner = Runner([scorer, mediator])
    result = runner.run(inputs)
    return result

