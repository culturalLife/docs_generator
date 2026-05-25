"""
summarize_data.py — JSON Payload → Markdown Summary
=====================================================
Converts the consulting questionnaire JSON (data.json) into a structured
markdown string that is injected into the Mistral system prompt.

Production changes from original:
  - Hardcoded absolute paths removed — uses config.JSON_PAYLOAD_PATH
  - Input validation added: checks required top-level keys before processing
  - Errors are raised as ValueError so the API layer can return a clean 400/500
"""

import json
from pathlib import Path
from typing import Any, Dict

# pyrefly: ignore [missing-import]
import config
# pyrefly: ignore [missing-import]
from logger import get_logger

logger = get_logger(__name__)

# Required top-level keys we expect in the JSON payload
_REQUIRED_KEYS = ["framework_name", "framework_version", "assessment", "gates"]


def validate_payload(data: Dict[str, Any]) -> None:
    """
    Validates that the JSON payload has the expected structure.
    Raises ValueError with a descriptive message if validation fails.
    """
    missing = [k for k in _REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(
            f"JSON payload is missing required keys: {missing}. "
            f"Expected keys: {_REQUIRED_KEYS}"
        )

    assessment = data.get("assessment", {})
    if not isinstance(assessment, dict):
        raise ValueError("'assessment' field must be a JSON object (dict).")

    gates = data.get("gates", [])
    if not isinstance(gates, list) or len(gates) == 0:
        raise ValueError("'gates' field must be a non-empty list.")

    logger.debug(f"Payload validation passed | framework={data.get('framework_name')} | gates={len(gates)}")


def clean_data_summary(data: Dict[str, Any]) -> str:
    """
    Converts the raw JSON payload dict into a structured markdown string.

    Args:
        data: Parsed JSON dict from data.json (or POSTed payload in API-driven mode).

    Returns:
        A multi-line markdown string ready to be injected as LLM context.

    Raises:
        ValueError: If the payload is missing required keys or has unexpected structure.
    """
    validate_payload(data)

    lines = []
    lines.append(f"# {data.get('framework_name')} - Summarized Input Data")
    lines.append(f"**Framework Version:** {data.get('framework_version')}")
    lines.append(f"**Client:** {data.get('assessment', {}).get('client')}")
    lines.append(f"**Use Case/Assessment Name:** {data.get('assessment', {}).get('name')}")
    lines.append(f"**Industry:** {data.get('assessment', {}).get('industry')}")
    lines.append(f"**Lead Consultant:** {data.get('assessment', {}).get('lead_consultant')}")
    lines.append(
        f"**Overall Status:** {data.get('assessment', {}).get('overall_status')} "
        f"({data.get('assessment', {}).get('overall_status_code')})"
    )
    lines.append(f"**Started At:** {data.get('assessment', {}).get('started_at')}")
    lines.append(f"**Last Updated At:** {data.get('assessment', {}).get('last_updated_at')}")
    lines.append("\n---\n")

    for gate in data.get("gates", []):
        gate_num = gate.get("gate_number")
        gate_title = gate.get("gate_title")
        gate_status = gate.get("gate_status")
        gate_purpose = gate.get("gate_purpose")
        owners = ", ".join(gate.get("owners", []))
        deliverable = gate.get("deliverable")

        lines.append(f"## Gate {gate_num}: {gate_title}")
        lines.append(f"- **Purpose:** {gate_purpose}")
        lines.append(f"- **Owners:** {owners}")
        lines.append(f"- **Deliverable:** {deliverable}")
        lines.append(f"- **Gate Status:** {gate_status} ({gate.get('gate_status_code')})")
        lines.append("")

        for dim in gate.get("dimensions", []):
            tag = dim.get("dimension_tag")
            title = dim.get("dimension_title")
            purpose = dim.get("dimension_purpose")
            status = dim.get("dimension_status")
            obs = dim.get("consulting_observation")
            notes = dim.get("detailed_notes")

            lines.append(f"### Dimension {tag}: {title}")
            lines.append(f"- **Purpose:** {purpose}")
            lines.append(f"- **Status:** {status} ({dim.get('dimension_status_code')})")
            if obs:
                lines.append(f"- **Consulting Observation:** *\"{obs.strip()}\"*")
            if notes:
                lines.append(f"- **Detailed Notes:** *\"{notes.strip()}\"*")
            lines.append("")

            questions = dim.get("questions", [])
            if questions:
                lines.append("| Question ID | Question Text | Answer | Answer Label |")
                lines.append("|---|---|---|---|")
                for q in questions:
                    qid = q.get("question_id")
                    text = q.get("question_text")
                    ans = q.get("raw_answer")
                    label = q.get("answer_label")
                    ans_str = ", ".join(ans) if isinstance(ans, list) else str(ans)
                    lines.append(f"| {qid} | {text} | {ans_str} | {label} |")
                lines.append("")

        lines.append("\n---\n")

    summary = "\n".join(lines)
    logger.debug(f"Data summary generated | chars={len(summary)}")
    return summary


def load_and_summarize() -> str:
    """
    Convenience function: loads data.json from config path and returns summary.
    Used for local testing or when called outside the API context.
    """
    json_path: Path = config.JSON_PAYLOAD_PATH
    if not json_path.exists():
        raise FileNotFoundError(f"JSON payload not found at: {json_path}")

    logger.info(f"Loading JSON payload from {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return clean_data_summary(data)


if __name__ == "__main__":
    # Quick local test: summarize data.json and print to stdout
    print(load_and_summarize())
