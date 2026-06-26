"""Prompt registry and builders (PROMPT_VERSION wiring)."""

from __future__ import annotations

from app.llm.prompts import v1

CURRENT_PROMPT_VERSION = v1.PROMPT_VERSION


def build_followup_prompt(emotions: str, text: str) -> str:
    """Build the verbatim follow-up prompt with substitutions."""
    return v1.FOLLOWUP_PROMPT_TEMPLATE.replace("<emotions>", emotions).replace("<text>", text)


def build_analysis_prompt(emotions: str, text: str) -> str:
    """Build the verbatim analysis prompt with substitutions."""
    return v1.ANALYSIS_PROMPT_TEMPLATE.replace("<emotions>", emotions).replace("<text>", text)
