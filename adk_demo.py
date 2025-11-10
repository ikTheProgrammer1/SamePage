"""
Optional ADK wiring demo for judges.

Defines how Scorer and Mediator would be discovered and inspected via ADK.
Not used in the runtime path by default.
"""

from typing import Any, Dict


def example_adk_locations() -> Dict[str, Any]:
    try:
        import google.adk  # type: ignore  # noqa: F401
        return {
            "scorer_path": "src/samepage_app/agents/scorer",
            "mediator_path": "src/samepage_app/agents/mediator",
            "cli_web": "adk web <path>",
            "cli_run": "adk run <path>",
        }
    except Exception:
        return {"error": "google.adk not installed"}
