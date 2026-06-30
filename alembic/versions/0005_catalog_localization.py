"""Catalog localization + full 100-emotion set (ADR-010).

Revision ID: 0005_catalog_localization
Revises: 0004_device_id_string
Create Date: 2026-06-26

Non-destructive (docs/03-data-model §Миграция каталога):
1. Schema (batch_alter_table on both backends; PostgreSQL recreate='auto' ->
   plain online ALTER RENAME/ADD, metadata-only): rename ``label`` -> ``label_en``
   and add ``label_ru`` NULLABLE on mood_scale_levels and emotions.
2. Backfill emotions.label_ru = label_en (legacy rows; they get deactivated).
3. Update mood_scale_levels: value=3 code okay->neutral / Neutral, value=5 code
   great->awesome / Awesome; set RU labels for all five.
4. Deactivate every existing emotion (is_active=false) — legacy emotions are kept
   (NOT deleted) so old entry_emotions FKs survive.
5. Insert the new 100 localized emotions, idempotently by ``code``.
6. SET NOT NULL on label_ru.

Data is inlined (frozen snapshot) — a historical migration must stay reproducible
regardless of later changes to app.seed.catalog_seed.

Downgrade is reversible without data loss (reactivate legacy, delete the 100 new,
revert level codes/labels, drop label_ru, rename label_en -> label).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_catalog_localization"
down_revision: str | None = "0004_device_id_string"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (value, code, label_en, label_ru) — final localized levels.
_LEVELS = [
    (1, "terrible", "Terrible", "Ужасно"),
    (2, "bad", "Bad", "Плохо"),
    (3, "neutral", "Neutral", "Нейтрально"),
    (4, "good", "Good", "Хорошо"),
    (5, "awesome", "Awesome", "Отлично"),
]

# (code, label_en, label_ru, level_value, order) — final 100 emotions (frozen).
_EMOTIONS = [
    ("terrible_devastated", "Devastated", "Опустошённый", 1, 1),
    ("terrible_panicked", "Panicked", "В панике", 1, 2),
    ("terrible_terrified", "Terrified", "В ужасе", 1, 3),
    ("terrible_hopeless", "Hopeless", "Безнадёжный", 1, 4),
    ("terrible_heartbroken", "Heartbroken", "Убитый горем", 1, 5),
    ("terrible_overwhelmed", "Overwhelmed", "Перегруженный", 1, 6),
    ("terrible_furious", "Furious", "В ярости", 1, 7),
    ("terrible_miserable", "Miserable", "Несчастный", 1, 8),
    ("terrible_helpless", "Helpless", "Беспомощный", 1, 9),
    ("terrible_trapped", "Trapped", "В ловушке", 1, 10),
    ("terrible_humiliated", "Humiliated", "Униженный", 1, 11),
    ("terrible_rejected", "Rejected", "Отвергнутый", 1, 12),
    ("terrible_desperate", "Desperate", "В отчаянии", 1, 13),
    ("terrible_anguished", "Anguished", "Измученный", 1, 14),
    ("terrible_grieving", "Grieving", "Скорбящий", 1, 15),
    ("terrible_shattered", "Shattered", "Разбитый", 1, 16),
    ("terrible_enraged", "Enraged", "В бешенстве", 1, 17),
    ("terrible_dread", "Dread", "В страхе", 1, 18),
    ("terrible_numb", "Numb", "Оцепеневший", 1, 19),
    ("terrible_abandoned", "Abandoned", "Покинутый", 1, 20),
    ("bad_frustrated", "Frustrated", "Раздражённый", 2, 1),
    ("bad_stressed", "Stressed", "В стрессе", 2, 2),
    ("bad_disappointed", "Disappointed", "Разочарованный", 2, 3),
    ("bad_sad", "Sad", "Грустный", 2, 4),
    ("bad_worried", "Worried", "Обеспокоенный", 2, 5),
    ("bad_irritated", "Irritated", "Раздосадованный", 2, 6),
    ("bad_tense", "Tense", "Напряжённый", 2, 7),
    ("bad_discouraged", "Discouraged", "Обескураженный", 2, 8),
    ("bad_insecure", "Insecure", "Неуверенный", 2, 9),
    ("bad_confused", "Confused", "Растерянный", 2, 10),
    ("bad_lonely", "Lonely", "Одинокий", 2, 11),
    ("bad_guilty", "Guilty", "Виноватый", 2, 12),
    ("bad_embarrassed", "Embarrassed", "Смущённый", 2, 13),
    ("bad_jealous", "Jealous", "Ревнивый", 2, 14),
    ("bad_bored", "Bored", "Скучающий", 2, 15),
    ("bad_restless", "Restless", "Беспокойный", 2, 16),
    ("bad_uncomfortable", "Uncomfortable", "Некомфортно", 2, 17),
    ("bad_impatient", "Impatient", "Нетерпеливый", 2, 18),
    ("bad_resentful", "Resentful", "Обиженный", 2, 19),
    ("bad_apathetic", "Apathetic", "Апатичный", 2, 20),
    ("neutral_calm", "Calm", "Спокойный", 3, 1),
    ("neutral_okay", "Okay", "Нормально", 3, 2),
    ("neutral_neutral", "Neutral", "Нейтральный", 3, 3),
    ("neutral_indifferent", "Indifferent", "Безразличный", 3, 4),
    ("neutral_thoughtful", "Thoughtful", "Задумчивый", 3, 5),
    ("neutral_curious", "Curious", "Любопытный", 3, 6),
    ("neutral_focused", "Focused", "Сосредоточенный", 3, 7),
    ("neutral_tired", "Tired", "Уставший", 3, 8),
    ("neutral_nostalgic", "Nostalgic", "Ностальгирующий", 3, 9),
    ("neutral_uncertain", "Uncertain", "Неуверенный", 3, 10),
    ("neutral_reserved", "Reserved", "Сдержанный", 3, 11),
    ("neutral_reflective", "Reflective", "Размышляющий", 3, 12),
    ("neutral_distracted", "Distracted", "Рассеянный", 3, 13),
    ("neutral_patient", "Patient", "Терпеливый", 3, 14),
    ("neutral_composed", "Composed", "Уравновешенный", 3, 15),
    ("neutral_detached", "Detached", "Отстранённый", 3, 16),
    ("neutral_surprised", "Surprised", "Удивлённый", 3, 17),
    ("neutral_pensive", "Pensive", "Погружённый в мысли", 3, 18),
    ("neutral_observant", "Observant", "Наблюдательный", 3, 19),
    ("neutral_expectant", "Expectant", "В ожидании", 3, 20),
    ("good_happy", "Happy", "Счастливый", 4, 1),
    ("good_relaxed", "Relaxed", "Расслабленный", 4, 2),
    ("good_grateful", "Grateful", "Благодарный", 4, 3),
    ("good_content", "Content", "Довольный", 4, 4),
    ("good_hopeful", "Hopeful", "С надеждой", 4, 5),
    ("good_confident", "Confident", "Уверенный", 4, 6),
    ("good_motivated", "Motivated", "Мотивированный", 4, 7),
    ("good_peaceful", "Peaceful", "Умиротворённый", 4, 8),
    ("good_cheerful", "Cheerful", "Весёлый", 4, 9),
    ("good_inspired", "Inspired", "Вдохновлённый", 4, 10),
    ("good_connected", "Connected", "Близость с людьми", 4, 11),
    ("good_supported", "Supported", "Чувствующий поддержку", 4, 12),
    ("good_trusting", "Trusting", "Доверяющий", 4, 13),
    ("good_warm", "Warm", "С душевным теплом", 4, 14),
    ("good_proud", "Proud", "Гордый", 4, 15),
    ("good_optimistic", "Optimistic", "Оптимистичный", 4, 16),
    ("good_energized", "Energized", "Энергичный", 4, 17),
    ("good_interested", "Interested", "Заинтересованный", 4, 18),
    ("good_relieved", "Relieved", "Испытывающий облегчение", 4, 19),
    ("good_affectionate", "Affectionate", "Нежный", 4, 20),
    ("awesome_joyful", "Joyful", "Радостный", 5, 1),
    ("awesome_excited", "Excited", "В предвкушении", 5, 2),
    ("awesome_thrilled", "Thrilled", "В восторге", 5, 3),
    ("awesome_delighted", "Delighted", "Очень довольный", 5, 4),
    ("awesome_elated", "Elated", "Ликующий", 5, 5),
    ("awesome_empowered", "Empowered", "Уверенный в своих силах", 5, 6),
    ("awesome_fulfilled", "Fulfilled", "Реализованный", 5, 7),
    ("awesome_loved", "Loved", "Любимый", 5, 8),
    ("awesome_radiant", "Radiant", "Сияющий", 5, 9),
    ("awesome_enthusiastic", "Enthusiastic", "Воодушевлённый", 5, 10),
    ("awesome_passionate", "Passionate", "Увлечённый", 5, 11),
    ("awesome_playful", "Playful", "Игривый", 5, 12),
    ("awesome_adventurous", "Adventurous", "Готовый к приключениям", 5, 13),
    ("awesome_blissful", "Blissful", "Блаженный", 5, 14),
    ("awesome_strong", "Strong", "Сильный", 5, 15),
    ("awesome_accomplished", "Accomplished", "Гордый результатом", 5, 16),
    ("awesome_vibrant", "Vibrant", "Полный жизни", 5, 17),
    ("awesome_free", "Free", "Свободный", 5, 18),
    ("awesome_overjoyed", "Overjoyed", "Переполненный радостью", 5, 19),
    ("awesome_ecstatic", "Ecstatic", "В эйфории", 5, 20),
]

_levels_tbl = sa.table(
    "mood_scale_levels",
    sa.column("id", sa.Uuid()),
    sa.column("value", sa.Integer()),
    sa.column("code", sa.String()),
    sa.column("label_en", sa.String()),
    sa.column("label_ru", sa.String()),
)

_emotions_tbl = sa.table(
    "emotions",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.String()),
    sa.column("label_en", sa.String()),
    sa.column("label_ru", sa.String()),
    sa.column("scale_level_id", sa.Uuid()),
    sa.column("order", sa.Integer()),
    sa.column("is_active", sa.Boolean()),
)


def upgrade() -> None:
    # 1. Schema: rename label -> label_en, add label_ru (nullable for backfill).
    for table in ("mood_scale_levels", "emotions"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "label",
                new_column_name="label_en",
                existing_type=sa.String(length=100),
                existing_nullable=False,
            )
            batch_op.add_column(sa.Column("label_ru", sa.String(length=100), nullable=True))

    # 2. Backfill RU labels of legacy emotions (they get deactivated anyway).
    op.execute(
        _emotions_tbl.update()
        .where(_emotions_tbl.c.label_ru.is_(None))
        .values(label_ru=_emotions_tbl.c.label_en)
    )

    # 3. Update level codes/labels (3/5 codes changed) + RU labels for all five.
    for value, code, label_en, label_ru in _LEVELS:
        op.execute(
            _levels_tbl.update()
            .where(_levels_tbl.c.value == value)
            .values(code=code, label_en=label_en, label_ru=label_ru)
        )

    # 4. Deactivate every existing emotion (legacy rows kept for entry_emotions FKs).
    op.execute(_emotions_tbl.update().values(is_active=False))

    # 5. Insert the 100 new localized emotions, idempotently by code.
    bind = op.get_bind()
    existing_codes = set(bind.execute(sa.select(_emotions_tbl.c.code)).scalars().all())
    level_id_by_value = {
        row.value: row.id
        for row in bind.execute(sa.select(_levels_tbl.c.value, _levels_tbl.c.id))
    }
    rows = [
        {
            "id": uuid.uuid4(),
            "code": code,
            "label_en": label_en,
            "label_ru": label_ru,
            "scale_level_id": level_id_by_value[level_value],
            "order": order,
            "is_active": True,
        }
        for code, label_en, label_ru, level_value, order in _EMOTIONS
        if code not in existing_codes
    ]
    if rows:
        op.bulk_insert(_emotions_tbl, rows)

    # 6. Enforce NOT NULL on label_ru after backfill.
    for table in ("mood_scale_levels", "emotions"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "label_ru", existing_type=sa.String(length=100), nullable=False
            )


def downgrade() -> None:
    # Remove the 100 new emotions and reactivate the legacy ones.
    new_codes = [code for code, *_ in _EMOTIONS]
    op.execute(_emotions_tbl.delete().where(_emotions_tbl.c.code.in_(new_codes)))
    op.execute(_emotions_tbl.update().values(is_active=True))

    # Revert level codes/labels for 3 and 5 (label_ru is dropped below).
    op.execute(
        _levels_tbl.update().where(_levels_tbl.c.value == 3).values(code="okay", label_en="Okay")
    )
    op.execute(
        _levels_tbl.update().where(_levels_tbl.c.value == 5).values(code="great", label_en="Great")
    )

    # Schema: drop label_ru, rename label_en -> label.
    for table in ("emotions", "mood_scale_levels"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("label_ru")
            batch_op.alter_column(
                "label_en",
                new_column_name="label",
                existing_type=sa.String(length=100),
                existing_nullable=False,
            )
