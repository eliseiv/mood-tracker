"""Domain enums stored as VARCHAR (cross-database, see docs/04-api-contract.md §4)."""

from __future__ import annotations

from enum import StrEnum


class EntryStatus(StrEnum):
    """Lifecycle states of a MoodEntry (ADR-003, 2-POST lifecycle).

    POST /entries creates the entry directly in ``awaiting_answer`` (after a
    successful LLM#1 follow-up); POST /entries/{id}/finish moves it to
    ``finished``.
    """

    AWAITING_ANSWER = "awaiting_answer"
    FINISHED = "finished"


class MessageRole(StrEnum):
    """Role of an EntryMessage."""

    USER_DESCRIPTION = "user_description"
    AI_FOLLOWUP = "ai_followup"
    USER_FOLLOWUP_ANSWER = "user_followup_answer"


class MessageSource(StrEnum):
    """Input source for user-authored messages."""

    TEXT = "text"
    VOICE = "voice"


class PointsReason(StrEnum):
    """Reason for a PointsLedger entry."""

    ENTRY_FINISHED = "entry_finished"
