from __future__ import annotations

import asyncio
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Activity, Emotion, MoodScaleLevel
from app.db.session import get_sessionmaker


class LevelSeed(TypedDict):
    value: int
    code: str
    label: str
    order: int


class EmotionSeed(TypedDict):
    code: str
    label: str
    level_value: int
    order: int


class ActivitySeed(TypedDict):
    code: str
    label: str


MOOD_LEVELS: list[LevelSeed] = [
    {"value": 1, "code": "terrible", "label": "Terrible", "order": 1},
    {"value": 2, "code": "bad", "label": "Bad", "order": 2},
    {"value": 3, "code": "okay", "label": "Okay", "order": 3},
    {"value": 4, "code": "good", "label": "Good", "order": 4},
    {"value": 5, "code": "great", "label": "Great", "order": 5},
]

EMOTIONS: list[EmotionSeed] = [
    # Level 1 — terrible
    {"code": "anxious", "label": "Anxious", "level_value": 1, "order": 1},
    {"code": "angry", "label": "Angry", "level_value": 1, "order": 2},
    {"code": "hopeless", "label": "Hopeless", "level_value": 1, "order": 3},
    {"code": "overwhelmed", "label": "Overwhelmed", "level_value": 1, "order": 4},
    {"code": "devastated", "label": "Devastated", "level_value": 1, "order": 5},
    # Level 2 — bad
    {"code": "sad", "label": "Sad", "level_value": 2, "order": 1},
    {"code": "tired", "label": "Tired", "level_value": 2, "order": 2},
    {"code": "stressed", "label": "Stressed", "level_value": 2, "order": 3},
    {"code": "frustrated", "label": "Frustrated", "level_value": 2, "order": 4},
    {"code": "lonely", "label": "Lonely", "level_value": 2, "order": 5},
    # Level 3 — okay
    {"code": "neutral", "label": "Neutral", "level_value": 3, "order": 1},
    {"code": "calm", "label": "Calm", "level_value": 3, "order": 2},
    {"code": "bored", "label": "Bored", "level_value": 3, "order": 3},
    {"code": "unsure", "label": "Unsure", "level_value": 3, "order": 4},
    {"code": "content", "label": "Content", "level_value": 3, "order": 5},
    # Level 4 — good
    {"code": "happy", "label": "Happy", "level_value": 4, "order": 1},
    {"code": "relaxed", "label": "Relaxed", "level_value": 4, "order": 2},
    {"code": "motivated", "label": "Motivated", "level_value": 4, "order": 3},
    {"code": "hopeful", "label": "Hopeful", "level_value": 4, "order": 4},
    {"code": "grateful", "label": "Grateful", "level_value": 4, "order": 5},
    # Level 5 — great
    {"code": "joyful", "label": "Joyful", "level_value": 5, "order": 1},
    {"code": "excited", "label": "Excited", "level_value": 5, "order": 2},
    {"code": "energetic", "label": "Energetic", "level_value": 5, "order": 3},
    {"code": "proud", "label": "Proud", "level_value": 5, "order": 4},
    {"code": "loved", "label": "Loved", "level_value": 5, "order": 5},
]

ACTIVITIES: list[ActivitySeed] = [
    {"code": "work", "label": "Work"},
    {"code": "study", "label": "Study"},
    {"code": "sport", "label": "Sport"},
    {"code": "yoga", "label": "Yoga"},
    {"code": "reading", "label": "Reading"},
    {"code": "friends", "label": "Friends"},
    {"code": "family", "label": "Family"},
    {"code": "music", "label": "Music"},
    {"code": "cooking", "label": "Cooking"},
    {"code": "walking", "label": "Walking"},
    {"code": "meditation", "label": "Meditation"},
    {"code": "gaming", "label": "Gaming"},
    {"code": "travel", "label": "Travel"},
    {"code": "nature", "label": "Nature"},
    {"code": "sleep", "label": "Sleep"},
]


async def seed_catalog(session: AsyncSession) -> None:
    """Insert predefined catalog rows. Idempotent: existing rows are skipped."""
    for level in MOOD_LEVELS:
        existing = await session.scalar(
            select(MoodScaleLevel).where(MoodScaleLevel.code == level["code"])
        )
        if existing is None:
            session.add(
                MoodScaleLevel(
                    value=level["value"],
                    code=level["code"],
                    label=level["label"],
                    order=level["order"],
                )
            )
    await session.flush()

    level_ids = {lvl.value: lvl.id for lvl in (await session.scalars(select(MoodScaleLevel))).all()}

    for emotion in EMOTIONS:
        existing_emotion = await session.scalar(
            select(Emotion).where(Emotion.code == emotion["code"])
        )
        if existing_emotion is None:
            session.add(
                Emotion(
                    code=emotion["code"],
                    label=emotion["label"],
                    scale_level_id=level_ids[emotion["level_value"]],
                    order=emotion["order"],
                    is_active=True,
                )
            )

    for activity in ACTIVITIES:
        existing_activity = await session.scalar(
            select(Activity).where(
                Activity.device_id.is_(None),
                func.lower(Activity.label) == activity["label"].lower(),
            )
        )
        if existing_activity is None:
            session.add(
                Activity(
                    label=activity["label"],
                    code=activity["code"],
                    device_id=None,
                    is_custom=False,
                )
            )

    await session.commit()


async def _main() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await seed_catalog(session)


if __name__ == "__main__":
    asyncio.run(_main())
