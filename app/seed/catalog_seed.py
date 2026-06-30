"""Predefined catalog seed (ADR-010): 5 levels x 20 emotions = 100, EN+RU.

Single source of truth materialized from docs/modules/catalog/emotion_catalog.tsv.
Idempotent by ``code``. Used for fresh DBs and the startup seed; migration 0005
transforms the legacy catalog into this one and stays consistent with it.
"""

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
    label_en: str
    label_ru: str
    order: int


class EmotionSeed(TypedDict):
    code: str
    label_en: str
    label_ru: str
    level_value: int
    order: int


class ActivitySeed(TypedDict):
    code: str
    label: str


MOOD_LEVELS: list[LevelSeed] = [
    {"value": 1, "code": "terrible", "label_en": "Terrible", "label_ru": "Ужасно", "order": 1},
    {"value": 2, "code": "bad", "label_en": "Bad", "label_ru": "Плохо", "order": 2},
    {"value": 3, "code": "neutral", "label_en": "Neutral", "label_ru": "Нейтрально", "order": 3},
    {"value": 4, "code": "good", "label_en": "Good", "label_ru": "Хорошо", "order": 4},
    {"value": 5, "code": "awesome", "label_en": "Awesome", "label_ru": "Отлично", "order": 5},
]

EMOTIONS: list[EmotionSeed] = [
    # level 1
    {
        "code": "terrible_devastated",
        "label_en": "Devastated",
        "label_ru": "Опустошённый",
        "level_value": 1,
        "order": 1,
    },
    {
        "code": "terrible_panicked",
        "label_en": "Panicked",
        "label_ru": "В панике",
        "level_value": 1,
        "order": 2,
    },
    {
        "code": "terrible_terrified",
        "label_en": "Terrified",
        "label_ru": "В ужасе",
        "level_value": 1,
        "order": 3,
    },
    {
        "code": "terrible_hopeless",
        "label_en": "Hopeless",
        "label_ru": "Безнадёжный",
        "level_value": 1,
        "order": 4,
    },
    {
        "code": "terrible_heartbroken",
        "label_en": "Heartbroken",
        "label_ru": "Убитый горем",
        "level_value": 1,
        "order": 5,
    },
    {
        "code": "terrible_overwhelmed",
        "label_en": "Overwhelmed",
        "label_ru": "Перегруженный",
        "level_value": 1,
        "order": 6,
    },
    {
        "code": "terrible_furious",
        "label_en": "Furious",
        "label_ru": "В ярости",
        "level_value": 1,
        "order": 7,
    },
    {
        "code": "terrible_miserable",
        "label_en": "Miserable",
        "label_ru": "Несчастный",
        "level_value": 1,
        "order": 8,
    },
    {
        "code": "terrible_helpless",
        "label_en": "Helpless",
        "label_ru": "Беспомощный",
        "level_value": 1,
        "order": 9,
    },
    {
        "code": "terrible_trapped",
        "label_en": "Trapped",
        "label_ru": "В ловушке",
        "level_value": 1,
        "order": 10,
    },
    {
        "code": "terrible_humiliated",
        "label_en": "Humiliated",
        "label_ru": "Униженный",
        "level_value": 1,
        "order": 11,
    },
    {
        "code": "terrible_rejected",
        "label_en": "Rejected",
        "label_ru": "Отвергнутый",
        "level_value": 1,
        "order": 12,
    },
    {
        "code": "terrible_desperate",
        "label_en": "Desperate",
        "label_ru": "В отчаянии",
        "level_value": 1,
        "order": 13,
    },
    {
        "code": "terrible_anguished",
        "label_en": "Anguished",
        "label_ru": "Измученный",
        "level_value": 1,
        "order": 14,
    },
    {
        "code": "terrible_grieving",
        "label_en": "Grieving",
        "label_ru": "Скорбящий",
        "level_value": 1,
        "order": 15,
    },
    {
        "code": "terrible_shattered",
        "label_en": "Shattered",
        "label_ru": "Разбитый",
        "level_value": 1,
        "order": 16,
    },
    {
        "code": "terrible_enraged",
        "label_en": "Enraged",
        "label_ru": "В бешенстве",
        "level_value": 1,
        "order": 17,
    },
    {
        "code": "terrible_dread",
        "label_en": "Dread",
        "label_ru": "В страхе",
        "level_value": 1,
        "order": 18,
    },
    {
        "code": "terrible_numb",
        "label_en": "Numb",
        "label_ru": "Оцепеневший",
        "level_value": 1,
        "order": 19,
    },
    {
        "code": "terrible_abandoned",
        "label_en": "Abandoned",
        "label_ru": "Покинутый",
        "level_value": 1,
        "order": 20,
    },
    # level 2
    {
        "code": "bad_frustrated",
        "label_en": "Frustrated",
        "label_ru": "Раздражённый",
        "level_value": 2,
        "order": 1,
    },
    {
        "code": "bad_stressed",
        "label_en": "Stressed",
        "label_ru": "В стрессе",
        "level_value": 2,
        "order": 2,
    },
    {
        "code": "bad_disappointed",
        "label_en": "Disappointed",
        "label_ru": "Разочарованный",
        "level_value": 2,
        "order": 3,
    },
    {"code": "bad_sad", "label_en": "Sad", "label_ru": "Грустный", "level_value": 2, "order": 4},
    {
        "code": "bad_worried",
        "label_en": "Worried",
        "label_ru": "Обеспокоенный",
        "level_value": 2,
        "order": 5,
    },
    {
        "code": "bad_irritated",
        "label_en": "Irritated",
        "label_ru": "Раздосадованный",
        "level_value": 2,
        "order": 6,
    },
    {
        "code": "bad_tense",
        "label_en": "Tense",
        "label_ru": "Напряжённый",
        "level_value": 2,
        "order": 7,
    },
    {
        "code": "bad_discouraged",
        "label_en": "Discouraged",
        "label_ru": "Обескураженный",
        "level_value": 2,
        "order": 8,
    },
    {
        "code": "bad_insecure",
        "label_en": "Insecure",
        "label_ru": "Неуверенный",
        "level_value": 2,
        "order": 9,
    },
    {
        "code": "bad_confused",
        "label_en": "Confused",
        "label_ru": "Растерянный",
        "level_value": 2,
        "order": 10,
    },
    {
        "code": "bad_lonely",
        "label_en": "Lonely",
        "label_ru": "Одинокий",
        "level_value": 2,
        "order": 11,
    },
    {
        "code": "bad_guilty",
        "label_en": "Guilty",
        "label_ru": "Виноватый",
        "level_value": 2,
        "order": 12,
    },
    {
        "code": "bad_embarrassed",
        "label_en": "Embarrassed",
        "label_ru": "Смущённый",
        "level_value": 2,
        "order": 13,
    },
    {
        "code": "bad_jealous",
        "label_en": "Jealous",
        "label_ru": "Ревнивый",
        "level_value": 2,
        "order": 14,
    },
    {
        "code": "bad_bored",
        "label_en": "Bored",
        "label_ru": "Скучающий",
        "level_value": 2,
        "order": 15,
    },
    {
        "code": "bad_restless",
        "label_en": "Restless",
        "label_ru": "Беспокойный",
        "level_value": 2,
        "order": 16,
    },
    {
        "code": "bad_uncomfortable",
        "label_en": "Uncomfortable",
        "label_ru": "Некомфортно",
        "level_value": 2,
        "order": 17,
    },
    {
        "code": "bad_impatient",
        "label_en": "Impatient",
        "label_ru": "Нетерпеливый",
        "level_value": 2,
        "order": 18,
    },
    {
        "code": "bad_resentful",
        "label_en": "Resentful",
        "label_ru": "Обиженный",
        "level_value": 2,
        "order": 19,
    },
    {
        "code": "bad_apathetic",
        "label_en": "Apathetic",
        "label_ru": "Апатичный",
        "level_value": 2,
        "order": 20,
    },
    # level 3
    {
        "code": "neutral_calm",
        "label_en": "Calm",
        "label_ru": "Спокойный",
        "level_value": 3,
        "order": 1,
    },
    {
        "code": "neutral_okay",
        "label_en": "Okay",
        "label_ru": "Нормально",
        "level_value": 3,
        "order": 2,
    },
    {
        "code": "neutral_neutral",
        "label_en": "Neutral",
        "label_ru": "Нейтральный",
        "level_value": 3,
        "order": 3,
    },
    {
        "code": "neutral_indifferent",
        "label_en": "Indifferent",
        "label_ru": "Безразличный",
        "level_value": 3,
        "order": 4,
    },
    {
        "code": "neutral_thoughtful",
        "label_en": "Thoughtful",
        "label_ru": "Задумчивый",
        "level_value": 3,
        "order": 5,
    },
    {
        "code": "neutral_curious",
        "label_en": "Curious",
        "label_ru": "Любопытный",
        "level_value": 3,
        "order": 6,
    },
    {
        "code": "neutral_focused",
        "label_en": "Focused",
        "label_ru": "Сосредоточенный",
        "level_value": 3,
        "order": 7,
    },
    {
        "code": "neutral_tired",
        "label_en": "Tired",
        "label_ru": "Уставший",
        "level_value": 3,
        "order": 8,
    },
    {
        "code": "neutral_nostalgic",
        "label_en": "Nostalgic",
        "label_ru": "Ностальгирующий",
        "level_value": 3,
        "order": 9,
    },
    {
        "code": "neutral_uncertain",
        "label_en": "Uncertain",
        "label_ru": "Неуверенный",
        "level_value": 3,
        "order": 10,
    },
    {
        "code": "neutral_reserved",
        "label_en": "Reserved",
        "label_ru": "Сдержанный",
        "level_value": 3,
        "order": 11,
    },
    {
        "code": "neutral_reflective",
        "label_en": "Reflective",
        "label_ru": "Размышляющий",
        "level_value": 3,
        "order": 12,
    },
    {
        "code": "neutral_distracted",
        "label_en": "Distracted",
        "label_ru": "Рассеянный",
        "level_value": 3,
        "order": 13,
    },
    {
        "code": "neutral_patient",
        "label_en": "Patient",
        "label_ru": "Терпеливый",
        "level_value": 3,
        "order": 14,
    },
    {
        "code": "neutral_composed",
        "label_en": "Composed",
        "label_ru": "Уравновешенный",
        "level_value": 3,
        "order": 15,
    },
    {
        "code": "neutral_detached",
        "label_en": "Detached",
        "label_ru": "Отстранённый",
        "level_value": 3,
        "order": 16,
    },
    {
        "code": "neutral_surprised",
        "label_en": "Surprised",
        "label_ru": "Удивлённый",
        "level_value": 3,
        "order": 17,
    },
    {
        "code": "neutral_pensive",
        "label_en": "Pensive",
        "label_ru": "Погружённый в мысли",
        "level_value": 3,
        "order": 18,
    },
    {
        "code": "neutral_observant",
        "label_en": "Observant",
        "label_ru": "Наблюдательный",
        "level_value": 3,
        "order": 19,
    },
    {
        "code": "neutral_expectant",
        "label_en": "Expectant",
        "label_ru": "В ожидании",
        "level_value": 3,
        "order": 20,
    },
    # level 4
    {
        "code": "good_happy",
        "label_en": "Happy",
        "label_ru": "Счастливый",
        "level_value": 4,
        "order": 1,
    },
    {
        "code": "good_relaxed",
        "label_en": "Relaxed",
        "label_ru": "Расслабленный",
        "level_value": 4,
        "order": 2,
    },
    {
        "code": "good_grateful",
        "label_en": "Grateful",
        "label_ru": "Благодарный",
        "level_value": 4,
        "order": 3,
    },
    {
        "code": "good_content",
        "label_en": "Content",
        "label_ru": "Довольный",
        "level_value": 4,
        "order": 4,
    },
    {
        "code": "good_hopeful",
        "label_en": "Hopeful",
        "label_ru": "С надеждой",
        "level_value": 4,
        "order": 5,
    },
    {
        "code": "good_confident",
        "label_en": "Confident",
        "label_ru": "Уверенный",
        "level_value": 4,
        "order": 6,
    },
    {
        "code": "good_motivated",
        "label_en": "Motivated",
        "label_ru": "Мотивированный",
        "level_value": 4,
        "order": 7,
    },
    {
        "code": "good_peaceful",
        "label_en": "Peaceful",
        "label_ru": "Умиротворённый",
        "level_value": 4,
        "order": 8,
    },
    {
        "code": "good_cheerful",
        "label_en": "Cheerful",
        "label_ru": "Весёлый",
        "level_value": 4,
        "order": 9,
    },
    {
        "code": "good_inspired",
        "label_en": "Inspired",
        "label_ru": "Вдохновлённый",
        "level_value": 4,
        "order": 10,
    },
    {
        "code": "good_connected",
        "label_en": "Connected",
        "label_ru": "Близость с людьми",
        "level_value": 4,
        "order": 11,
    },
    {
        "code": "good_supported",
        "label_en": "Supported",
        "label_ru": "Чувствующий поддержку",
        "level_value": 4,
        "order": 12,
    },
    {
        "code": "good_trusting",
        "label_en": "Trusting",
        "label_ru": "Доверяющий",
        "level_value": 4,
        "order": 13,
    },
    {
        "code": "good_warm",
        "label_en": "Warm",
        "label_ru": "С душевным теплом",
        "level_value": 4,
        "order": 14,
    },
    {
        "code": "good_proud",
        "label_en": "Proud",
        "label_ru": "Гордый",
        "level_value": 4,
        "order": 15,
    },
    {
        "code": "good_optimistic",
        "label_en": "Optimistic",
        "label_ru": "Оптимистичный",
        "level_value": 4,
        "order": 16,
    },
    {
        "code": "good_energized",
        "label_en": "Energized",
        "label_ru": "Энергичный",
        "level_value": 4,
        "order": 17,
    },
    {
        "code": "good_interested",
        "label_en": "Interested",
        "label_ru": "Заинтересованный",
        "level_value": 4,
        "order": 18,
    },
    {
        "code": "good_relieved",
        "label_en": "Relieved",
        "label_ru": "Испытывающий облегчение",
        "level_value": 4,
        "order": 19,
    },
    {
        "code": "good_affectionate",
        "label_en": "Affectionate",
        "label_ru": "Нежный",
        "level_value": 4,
        "order": 20,
    },
    # level 5
    {
        "code": "awesome_joyful",
        "label_en": "Joyful",
        "label_ru": "Радостный",
        "level_value": 5,
        "order": 1,
    },
    {
        "code": "awesome_excited",
        "label_en": "Excited",
        "label_ru": "В предвкушении",
        "level_value": 5,
        "order": 2,
    },
    {
        "code": "awesome_thrilled",
        "label_en": "Thrilled",
        "label_ru": "В восторге",
        "level_value": 5,
        "order": 3,
    },
    {
        "code": "awesome_delighted",
        "label_en": "Delighted",
        "label_ru": "Очень довольный",
        "level_value": 5,
        "order": 4,
    },
    {
        "code": "awesome_elated",
        "label_en": "Elated",
        "label_ru": "Ликующий",
        "level_value": 5,
        "order": 5,
    },
    {
        "code": "awesome_empowered",
        "label_en": "Empowered",
        "label_ru": "Уверенный в своих силах",
        "level_value": 5,
        "order": 6,
    },
    {
        "code": "awesome_fulfilled",
        "label_en": "Fulfilled",
        "label_ru": "Реализованный",
        "level_value": 5,
        "order": 7,
    },
    {
        "code": "awesome_loved",
        "label_en": "Loved",
        "label_ru": "Любимый",
        "level_value": 5,
        "order": 8,
    },
    {
        "code": "awesome_radiant",
        "label_en": "Radiant",
        "label_ru": "Сияющий",
        "level_value": 5,
        "order": 9,
    },
    {
        "code": "awesome_enthusiastic",
        "label_en": "Enthusiastic",
        "label_ru": "Воодушевлённый",
        "level_value": 5,
        "order": 10,
    },
    {
        "code": "awesome_passionate",
        "label_en": "Passionate",
        "label_ru": "Увлечённый",
        "level_value": 5,
        "order": 11,
    },
    {
        "code": "awesome_playful",
        "label_en": "Playful",
        "label_ru": "Игривый",
        "level_value": 5,
        "order": 12,
    },
    {
        "code": "awesome_adventurous",
        "label_en": "Adventurous",
        "label_ru": "Готовый к приключениям",
        "level_value": 5,
        "order": 13,
    },
    {
        "code": "awesome_blissful",
        "label_en": "Blissful",
        "label_ru": "Блаженный",
        "level_value": 5,
        "order": 14,
    },
    {
        "code": "awesome_strong",
        "label_en": "Strong",
        "label_ru": "Сильный",
        "level_value": 5,
        "order": 15,
    },
    {
        "code": "awesome_accomplished",
        "label_en": "Accomplished",
        "label_ru": "Гордый результатом",
        "level_value": 5,
        "order": 16,
    },
    {
        "code": "awesome_vibrant",
        "label_en": "Vibrant",
        "label_ru": "Полный жизни",
        "level_value": 5,
        "order": 17,
    },
    {
        "code": "awesome_free",
        "label_en": "Free",
        "label_ru": "Свободный",
        "level_value": 5,
        "order": 18,
    },
    {
        "code": "awesome_overjoyed",
        "label_en": "Overjoyed",
        "label_ru": "Переполненный радостью",
        "level_value": 5,
        "order": 19,
    },
    {
        "code": "awesome_ecstatic",
        "label_en": "Ecstatic",
        "label_ru": "В эйфории",
        "level_value": 5,
        "order": 20,
    },
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
    """Insert predefined catalog rows. Idempotent: existing rows (by code) skipped."""
    for level in MOOD_LEVELS:
        existing = await session.scalar(
            select(MoodScaleLevel).where(MoodScaleLevel.code == level["code"])
        )
        if existing is None:
            session.add(
                MoodScaleLevel(
                    value=level["value"],
                    code=level["code"],
                    label_en=level["label_en"],
                    label_ru=level["label_ru"],
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
                    label_en=emotion["label_en"],
                    label_ru=emotion["label_ru"],
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
