# 06 — Testing Strategy

## Пирамида

| Уровень | Покрытие | Инструмент |
|---|---|---|
| Unit | services (streak, points, language, валидаторы), llm-schema | pytest |
| Integration | routes + БД (SQLite in-memory/файл), миграции применяются | pytest + httpx ASGITransport |
| Contract | соответствие ответов схемам из [04-api-contract.md](04-api-contract.md) | pytest + pydantic |
| E2E (happy-path) | полный сценарий create→finish→history с замоканным OpenAI | pytest |

## Coverage gate

- Минимум **80%** строк по `app/` (`--cov-fail-under=80`).
- Критичные модули (streak, points, entry state machine) — стремимся к ~100% веток.

## Обязательные сценарии

### Entry state machine (2-POST, ADR-003)
- `POST /entries` создаёт `awaiting_answer` + follow-up (LLM#1 замокан); при ошибке LLM#1 запись не создаётся.
- `POST /finish` из `awaiting_answer` → `finished`.
- `POST /finish` из статуса ≠ `awaiting_answer` → `409 entry_invalid_transition` с `details.current_status`.
- Повторный `POST /finish` (запись уже `finished`) → `409 entry_already_finished`.
- Валидация `POST /entries`: отсутствует `mood`/`description` → `422`; эмоция не соответствует уровню `mood` → `422`; `emotions: []` валиден.

### Gamification (атомарность/идемпотентность)
- `POST /finish` начисляет ровно `POINTS_PER_ENTRY`, обновляет `points_balance` = сумме ledger.
- Повторный/двойной finish не дублирует очки.
- Streak: первый entry дня, серия последовательных дней, разрыв серии (по локальной дате + timezone), обновление `longest_streak`.
- (Postgres) Нет lost-update streak/points при конкурентном finish двух разных записей одного устройства (row-lock на `Device`, ADR-008).

### LLM (мокаются)
- Follow-up (LLM#1 в `POST /entries`): корректный prompt_version, текст в ответе.
- Анализ (LLM#2 в `POST /finish`): парсинг Structured Outputs; нарушение лимитов длины (title>3 слов / overview>40 слов) → 1 retry → при повторном провале мягкий обрез, finish успешен (`200`, не `502`).
- Таймаут/ошибка OpenAI на `POST /entries` → `502/503`, запись не создаётся; на `POST /finish` → статус остаётся `awaiting_answer`.

### Аутентификация/идентификация/безопасность
- Отсутствие `X-API-Key` → `401 api_key_required`; неверный → `401 api_key_invalid`; проверка **до** `X-Device-Id` (неверный ключ + отсутствующий/битый device-id → всё равно `401`, `Device` не создаётся).
- Валидный `X-API-Key` + `X-Device-Id`: пусто/только пробелы → `400 device_id_required`; длина >64 или символы вне `[A-Za-z0-9._-]` (пробел/`/`/не-ASCII/control) → `400 device_id_invalid`.
- `X-Device-Id` как произвольная строка (`testuser`) **и** как UUID → оба `200`; `GET /me` возвращает `device_id` ровно как прислан (echo); регистрозависимость (`TestUser` ≠ `testuser` — разные `Device`).
- `GET /health` без `X-API-Key` и без `X-Device-Id` → `200`.
- Доступ к чужому entry → `404`.
- Миграция UUID→String(64): существующие UUID-устройства сохраняются (`uuid::text`); новые строковые id создаются и скоупятся.

### Транскрипция
- Файл > 10 MB → `413`.
- MIME не из allow-list / битая сигнатура → `415`.
- Успех → `{ text, detected_language }`.

### Каталог
- `GET /moods`, `GET /activities` форматы.
- `POST /activities` дедуп → `409 activity_duplicate`.

### История
- Cursor-пагинация, порядок `finished_at DESC`, `next_cursor: null` на последней странице, битый cursor → `422`.

## Принципы

- OpenAI всегда замокан в тестах (никаких реальных вызовов / трат токенов).
- Тесты детерминированы; время/дата мокаются для streak.
- Каждый баг → регрессионный тест.
