"""Structured Outputs schema and payload model for the final analysis (ADR-005)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# Strict json_schema: every object sets additionalProperties=false and lists all
# properties as required (OpenAI Structured Outputs requirements).
ANALYSIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "overview": {"type": "string"},
        "advice": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["heading", "body"],
            },
        },
    },
    "required": ["title", "overview", "advice"],
}

ANALYSIS_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "mood_analysis",
        "strict": True,
        "schema": ANALYSIS_JSON_SCHEMA,
    },
}


class AdviceItem(BaseModel):
    """One advice section."""

    heading: str
    body: str


class AnalysisPayload(BaseModel):
    """Parsed LLM#2 structured payload."""

    title: str
    overview: str
    advice: list[AdviceItem]
