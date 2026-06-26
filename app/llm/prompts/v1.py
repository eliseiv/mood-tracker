"""Prompt templates v1 — copied verbatim from docs/modules/entries/README.md.

Tokens ``<emotions>`` and ``<text>`` are substituted at call time. Do NOT
edit the wording without bumping PROMPT_VERSION (ADR-005).
"""

from __future__ import annotations

PROMPT_VERSION = "v1"

# LLM#1 — empathic follow-up question (plain text response).
FOLLOWUP_PROMPT_TEMPLATE = (
    "Take into account that the person feels <emotions>. Ask a follow-up question "
    "about this user's message and show empathy up to 30 words long. "
    "User message <text>"
)

# LLM#2 — final analysis (OpenAI Structured Outputs).
ANALYSIS_PROMPT_TEMPLATE = (
    "Take into account that the person feels <emotions>. The user also wrote the "
    "following <text>. Please give me a three-part answer. In the first part, write "
    "a general title based on the information you received about the problem up to 3 "
    "words long. In the second part, provide an overview of up to 40 words. And in "
    "the third part, give advice on how to improve your well-being in this situation. "
    "The advice should be divided into sections. Answer in the language I'm asking "
    "you about the problem."
)
