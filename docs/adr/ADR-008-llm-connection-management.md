# ADR-008 — Трёхфазное управление DB-соединением при синхронных LLM-вызовах

Статус: accepted
Дата: 2026-06-26 (iteration 3); дополнено iteration 4 (2-POST lifecycle + Device row-lock).

## Context

Эндпоинты `POST /entries` (LLM#1 follow-up) и `POST /entries/{id}/finish` (LLM#2 анализ) выполняют синхронный сетевой вызов OpenAI внутри обработки запроса (2-POST lifecycle, ADR-003). В наивной реализации DB-соединение из пула удерживалось бы на всё время запроса, включая сетевой вызов LLM (`OPENAI_TIMEOUT_SECONDS` ~30 с). При конкурентной нагрузке это исчерпывает пул: число «занятых» соединений растёт пропорционально длительности LLM, а не объёму работы с БД. Проблема зафиксирована holistic-reviewer (finding #2, scalability).

Дополнительно:
- Повторный/конкурентный `finish` одной записи создаёт гонку: два запроса могут пройти status-guard до того, как первый закоммитит `status=finished`.
- **Streak/points lost-update** (prompt_issue backend iter4): `current_streak`/`longest_streak`/`last_entry_date` и `points_balance` обновляются read-modify-write в Python. При одновременном finish **двух разных записей одного устройства** без блокировки строки `Device` возможна потеря обновления (один finish перезаписывает результат другого).

## Decision

`POST /entries` и `POST /entries/{id}/finish` реализованы по **трёхфазному паттерну** (соединение из пула не удерживается во время LLM):

### `POST /entries` (создание + LLM#1)
1. **Фаза 1 — read-only tx**: валидация `mood`/`emotions`/`activities` по каталогу, сбор промта LLM#1. Соединение возвращается в пул.
2. **Фаза 2 — LLM#1 без соединения**: вызов OpenAI выполняется, когда соединение не удерживается (`pool.checkedout()==0` относительно запроса).
3. **Фаза 3 — write tx**: создаётся `MoodEntry(status=awaiting_answer)`, `entry_emotions`/`entry_activities`, `EntryMessage(user_description)` + `EntryMessage(ai_followup)`, upsert `Device.timezone`/`locale`. **Запись создаётся только при успехе LLM#1**; при ошибке — `502/503`, ничего не персистится, клиент повторяет `POST /entries`.

### `POST /entries/{id}/finish` (ответ + LLM#2)
1. **Фаза 1 — read-only tx**: загрузка записи, status-guard (`awaiting_answer`), сбор промта LLM#2 из `description` + `answer` (answer берётся из тела запроса, не сохраняется до фазы 3). Соединение возвращается в пул.
2. **Фаза 2 — LLM#2 без соединения**.
3. **Фаза 3 — write tx**: `SELECT ... FOR UPDATE OF mood_entries` по записи (повторный status-guard) **и** `SELECT ... FOR UPDATE` строки `Device` (`with_for_update`); сохраняются `EntryMessage(user_followup_answer)`, `AnalysisResult`+`AdviceSection`, начисление `POINTS_PER_ENTRY` (ledger + `points_balance`), пересчёт streak, `status→finished`, `finished_at`. При ошибке LLM#2 — `502/503`, ничего не персистится, статус остаётся `awaiting_answer`, клиент повторяет `POST /finish`.

**Блокировки в фазе 3 finish:**
- `FOR UPDATE OF mood_entries` — сериализует конкурентный/повторный finish одной записи (идемпотентность через повторный status-guard).
- `FOR UPDATE` строки `Device` — единый фикс для **двух** гонок read-modify-write на `Device`: `points_balance` и streak (`current_streak`/`longest_streak`/`last_entry_date`). Сериализует одновременный finish разных записей одного устройства, устраняя lost-update.

На **PostgreSQL** `FOR UPDATE` — реальная блокировка строки; на **SQLite** — no-op, что приемлемо для local/CI (конкуренции нет). Повторный status-guard в фазе 3 — основной механизм идемпотентности; блокировки предотвращают гонки чтения-записи.

## Consequences

- (+) Соединение не занято на время LLM → размер пула определяется короткими tx, а не `OPENAI_TIMEOUT_SECONDS`. Сервис масштабируется по конкурентным запросам без раздувания пула.
- (+) Конкурентный/повторный finish сериализуется и не дублирует points/streak; повторный finish finished-записи → `409`.
- (+) Блокировка строки `Device` закрывает обе гонки (points_balance и streak) одним механизмом, без отдельного TD.
- (+) При сбое LLM нет «полузаписей»: `POST /entries` не оставляет entry без follow-up, `finish` не оставляет частично финализированную запись.
- (−) Данные читаются дважды (фаза 1 и фаза 3); между фазами состояние могло измениться — поэтому status-guard в фазе 3 обязателен.
- (−) Поведение блокировки различается PostgreSQL ↔ SQLite; на SQLite сериализация не гарантируется (вне scope для local/CI).
- Pool sizing / `pool_timeout` рекомендации — [07-deployment.md](../07-deployment.md).

## Alternatives

- **Удерживать соединение на всё время запроса**: просто, но не масштабируется — отвергнуто (root cause finding #2).
- **Завести TD на удержание соединения / streak-гонку**: отвергнуто — обе проблемы устранены в коде (iteration 3–4), TD не нужен.
- **Отдельный advisory-lock / отдельная блокировка только для streak**: отвергнуто — `FOR UPDATE` строки `Device` уже сериализует и points, и streak одним приёмом.
- **Очередь/async-воркер для LLM**: избыточно для MVP-монолита (ADR-002).
