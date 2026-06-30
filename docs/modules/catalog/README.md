# Module: catalog

Status: in-progress

Справочники: шкала настроения + эмоции, активности. **built-in (предустановленный seed-каталог) = источник истины; activities расширяемы клиентом** через `POST /activities`.

**Каталог (финальный, датасет):** 5 уровней × 20 эмоций = **100 эмоций**, локализация EN+RU (ADR-010). Источник истины — [emotion_catalog.tsv](emotion_catalog.tsv) (колонки `mood_state`,`order`,`intensity_score`,`emotion_en`,`emotion_ru`,`suggested_key`). Полный список в docs **не дублируется** — материализуется в `app/seed/catalog_seed.py` и миграции 0005.

## Scope

- `GET /moods` — уровни 1..5 с эмоциями, **локализованные метки** (`?language=` → `Accept-Language` → `en`; ADR-010). Только `is_active=true`.
- `GET /activities` — built-in (глобальные) + кастомные устройства.
- `POST /activities` — создать кастомную активность с дедупом по `lower(label)` в пределах устройства.
- Seed built-in-данных: `app/seed/catalog_seed.py` (идемпотентно по `code`), материализует датасет (100 эмоций + 5 уровней с `label_en`/`label_ru`).

## Уровни и коды (датасет)

| value | code | label_en | label_ru |
|---|---|---|---|
| 1 | `terrible` | Terrible | Ужасно |
| 2 | `bad` | Bad | Плохо |
| 3 | `neutral` | Neutral | Нейтрально |
| 4 | `good` | Good | Хорошо |
| 5 | `awesome` | Awesome | Отлично |

> Коды уровней 3 и 5 изменены (было `okay`/`great`). `intensity_score` = `value`. RU-метки уровней — разумный дефолт, корректируемый.

Формат кода эмоции: `<level>_<emotion>` (= `suggested_key`), напр. `terrible_devastated`, `neutral_calm`, `awesome_ecstatic`. `order` — 1..20 внутри уровня.

## Out of scope

- Редактирование/удаление built-in-каталога клиентом (управляется seed/миграциями).
- Языки сверх EN/RU (расширение = новая колонка + миграция, ADR-010).

## API

См. [04-api-contract.md §6.2](../../04-api-contract.md) — `GET /moods` (локализация, формат ответа, коды уровней/эмоций).

## Data model

`MoodScaleLevel`, `Emotion`, `Activity` — см. [03-data-model.md](../../03-data-model.md). Локализация — колонки `label_en`/`label_ru` (ADR-010). Уникальность кастомных: `(device_id, lower(label))`; глобальных: `lower(label)` при `device_id IS NULL`.

## Миграция каталога (0005, non-destructive)

Полный план — [03-data-model.md §Миграция каталога](../../03-data-model.md). Кратко: rename `label`→`label_en` + add `label_ru` (batch, кросс-БД) → UPDATE уровней 3/5 (code/label) + RU-метки всем 5 → деактивация старых эмоций (`is_active=false`, **не удалять** — FK `entry_emotions`) → вставка 100 новых (идемпотентно по `code`) → NOT NULL `label_ru`. Применяется на живом prod-Postgres (`alembic upgrade head`), prod-данные не теряются.

## RBAC

- built-in — общие для всех.
- Кастомные активности видны/создаются только в скоупе своего `device-id`.

## DoD

- Дубликат кастомной активности → `409 activity_duplicate`.
- `GET /moods`/`GET /activities` соответствуют формату контракта.
- Seed идемпотентен (повторный запуск не дублирует).

## DoD (дополнено)

- `GET /moods` возвращает 5 уровней с кодами `terrible`/`bad`/`neutral`/`good`/`awesome` и 100 активных эмоций.
- Метки локализуются: `?language=ru` → RU, иначе EN; `code` не локализуется.
- Миграция 0005 non-destructive: старые `entry_emotions` сохранены, старые эмоции `is_active=false`.
- Seed и миграция согласованы с датасетом, идемпотентны по `code`.

## Open questions

- [Q-CATALOG-1](../../99-open-questions.md#q-catalog-1) — **resolved (финальный датасет)**: каталог зафиксирован — 5 уровней + 100 эмоций EN/RU из [emotion_catalog.tsv](emotion_catalog.tsv). Placeholder-статус снят.

## Changelog

- bootstrap: спроектирован модуль.
- iter 1: backend реализовал `GET /moods`, `GET/POST /activities`, seed-скаффолд.
- iter 3: Q-CATALOG-1 resolved-by-design — built-in baseline + client-custom activities; placeholder-seed приемлем, блокирующий статус снят.
- iter 9: **финальный каталог + локализация EN/RU** (ADR-010). 100 эмоций (5×20), коды уровней 3/5 → `neutral`/`awesome`, колонки `label_en`/`label_ru`, `GET /moods` локализуется по языку, миграция 0005 non-destructive. Q-CATALOG-1 resolved финальным датасетом. **Требует rework backend** (модели, миграция 0005, seed, `GET /moods`).
