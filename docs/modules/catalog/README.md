# Module: catalog

Status: in-progress

Справочники: шкала настроения + эмоции, активности. **built-in (предустановленный seed-каталог) = baseline-дефолт; activities расширяемы клиентом** через `POST /activities`.

## Scope

- `GET /moods` — уровни 1..5 с эмоциями.
- `GET /activities` — built-in (глобальные) + кастомные устройства.
- `POST /activities` — создать кастомную активность с дедупом по `lower(label)` в пределах устройства.
- Seed built-in-данных: `app/seed/catalog_seed.py` (идемпотентно). built-in = baseline; placeholder-набор приемлем (Q-CATALOG-1 resolved-by-design).

## Out of scope

- Редактирование/удаление built-in-каталога клиентом (управляется seed/миграциями).
- Локализация меток сверх того, что заложено в seed.

## API

См. [04-api-contract.md §6.2](../../04-api-contract.md).

## Data model

`MoodScaleLevel`, `Emotion`, `Activity` — см. [03-data-model.md](../../03-data-model.md). Уникальность кастомных: `(device_id, lower(label))`; глобальных: `lower(label)` при `device_id IS NULL`.

## RBAC

- built-in — общие для всех.
- Кастомные активности видны/создаются только в скоупе своего `device-id`.

## DoD

- Дубликат кастомной активности → `409 activity_duplicate`.
- `GET /moods`/`GET /activities` соответствуют формату контракта.
- Seed идемпотентен (повторный запуск не дублирует).

## Open questions

- [Q-CATALOG-1](../../99-open-questions.md#q-catalog-1) — **resolved-by-design**: built-in seed-каталог = baseline-дефолт, activities расширяемы клиентом через `POST /activities`. Точный визуальный перечень из Figma **не блокирует** — placeholder-набор приемлем, уточнение возможно позже. Допустима пометка `TODO(Q-CATALOG-1)` в seed как маркер будущего уточнения.

## Changelog

- bootstrap: спроектирован модуль.
- iter 1: backend реализовал `GET /moods`, `GET/POST /activities`, seed-скаффолд.
- iter 3: Q-CATALOG-1 resolved-by-design — built-in baseline + client-custom activities; placeholder-seed приемлем, блокирующий статус снят.
