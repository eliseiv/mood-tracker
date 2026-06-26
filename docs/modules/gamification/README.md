# Module: gamification

Status: in-progress

Очки и streak за завершённые записи.

## Scope

- Начисление очков: `POINTS_PER_ENTRY = 20` (Q-GAME-1) за `finish`, через append-only `PointsLedger` + денормализованный `Device.points_balance` в той же транзакции.
- Streak: `current_streak`, `longest_streak`, `last_entry_date` на `Device`; расчёт по локальной дате с учётом `Device.timezone` (Q-GAME-2).
- Чтение: `GET /me/points`, `GET /me/streak`.

## Out of scope

- Endpoints начисления напрямую (начисление только как часть транзакции `POST /finish` в модуле entries).
- Бейджи/уровни/магазин очков — вне scope на старте.

## Data model

`PointsLedger`, поля streak на `Device` — см. [03-data-model.md](../../03-data-model.md).

## Конкурентность (row-lock на Device, ADR-008)

Начисление очков и streak — read-modify-write по строке `Device` (`points_balance`, `current_streak`, `longest_streak`, `last_entry_date`). Чтобы исключить lost-update при **одновременном finish двух разных записей одного устройства**, транзакция фазы 3 finish берёт `SELECT ... FOR UPDATE` (`with_for_update`) на строке `Device` — это сериализует и points, и streak единым механизмом (без отдельного TD). Реальная блокировка на PostgreSQL, no-op на SQLite (local/CI без конкуренции). Решение зафиксировано в [ADR-008](../../adr/ADR-008-llm-connection-management.md).

## Логика

- **Очки**: при finish создаётся `PointsLedger(delta=+20, reason=entry_finished, entry_id)`; `points_balance += delta`. Идемпотентность: для пары `(entry_id, reason)` запись создаётся один раз; повторный finish не начисляет повторно (и сам по себе → `409`).
- **Streak**: вычисляется локальная дата finish по `Device.timezone`. `timezone` (IANA) задаётся клиентом через `POST /entries` (модуль identity делает upsert). Если `Device.timezone` == `null` или невалиден → fallback на **UTC**.
  - Если `last_entry_date` == сегодня → streak не меняется (несколько записей в день не увеличивают серию).
  - Если == вчера → `current_streak += 1`.
  - Иначе (разрыв или первая) → `current_streak = 1`.
  - `longest_streak = max(longest_streak, current_streak)`; `last_entry_date = сегодня`.

## RBAC

Скоуп по `device-id`.

## DoD

- Атомарность: очки/streak/анализ в одной транзакции finish.
- Идемпотентность: двойной finish не дублирует очки.
- Streak корректен для: первый день, последовательные дни, разрыв, несколько записей в день; учитывает timezone.
- Нет lost-update streak/points при одновременном finish двух разных записей одного устройства (row-lock на `Device`, ADR-008).

## Open questions

- [Q-GAME-1](../../99-open-questions.md#q-game-1) — +20 константа (дефолт).
- [Q-GAME-2](../../99-open-questions.md#q-game-2) — **resolved**: streak по локальной дате; `timezone` устанавливается через поле `timezone` в `POST /entries`, дефолт UTC.

## Changelog

- bootstrap: спроектирован модуль.
- iter 1: backend реализовал points + streak. Q-GAME-2 закрыт: `timezone` задаётся клиентом, дефолт UTC.
- iter 2: backend реализовал приём поля `timezone` и upsert `Device.timezone` (закрытие rework по Q-GAME-2).
- iter 4: добавлен `FOR UPDATE` строки `Device` в транзакции finish — фикс lost-update streak/points при конкурентном finish (ADR-008). `timezone` теперь принимается только в `POST /entries` (2-POST lifecycle, ADR-003). **Требует rework backend** (row-lock + убрать `PATCH /mood`).
