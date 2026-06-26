"""ORM -> response schema builders for entries and analysis."""

from __future__ import annotations

from app.db.models import AnalysisResult, MoodEntry
from app.schemas.entries import (
    AdviceOut,
    AnalysisOut,
    EntryActivityOut,
    EntryResponse,
    MessageOut,
)


def _emotion_codes(entry: MoodEntry) -> list[str]:
    return [emotion.code for emotion in entry.emotions]


def _activities_out(entry: MoodEntry) -> list[EntryActivityOut]:
    return [EntryActivityOut(id=activity.id, label=activity.label) for activity in entry.activities]


def analysis_to_out(analysis: AnalysisResult) -> AnalysisOut:
    """Build the analysis response object."""
    return AnalysisOut(
        title=analysis.title,
        overview=analysis.overview,
        advice=[
            AdviceOut(heading=section.heading, body=section.body)
            for section in analysis.advice_sections
        ],
        language=analysis.language,
        created_at=analysis.created_at,
    )


def entry_to_full_response(entry: MoodEntry) -> EntryResponse:
    """Build the full entry response (GET /entries/{id})."""
    return EntryResponse(
        id=entry.id,
        status=entry.status,
        mood=entry.mood_level.value,
        emotions=_emotion_codes(entry),
        activities=_activities_out(entry),
        language=entry.language,
        messages=[
            MessageOut(
                role=message.role,
                content=message.content,
                source=message.source,
                prompt_version=message.prompt_version,
                created_at=message.created_at,
            )
            for message in entry.messages
        ],
        analysis=analysis_to_out(entry.analysis) if entry.analysis is not None else None,
        created_at=entry.created_at,
        finished_at=entry.finished_at,
    )
