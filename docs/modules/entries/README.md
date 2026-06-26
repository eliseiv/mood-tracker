# Module: entries (+ LLM)

Status: in-progress

Жизненный цикл записи настроения, STT, follow-up и финальный анализ (интеграция с OpenAI).

## Scope

- State machine `MoodEntry` (ADR-003, 2-POST lifecycle): `[*] → awaiting_answer → finished`.
- Endpoints: `POST /entries` (создание + LLM#1 follow-up), `GET /entries/{id}`, `POST /entries/{id}/finish` (ответ + LLM#2 анализ), `GET /entries/{id}/analysis`, история `GET /entries?status=finished`.
- STT: `POST /transcriptions` (ADR-004).
- LLM: follow-up (текст) и анализ (Structured Outputs, ADR-005), выбор языка (ADR-006).

## Out of scope

- Начисление очков/streak (модуль gamification вызывается транзакционно из finish).
- Хранение аудио (Q-SEC-1 — не хранить).

## API

См. [04-api-contract.md §6.3–6.5](../../04-api-contract.md). State machine и happy-path — там же §5, §7. Два шага записи — `POST /entries` и `POST /entries/{id}/finish`; чтение (`GET /entries`, `GET /entries/{id}`, `GET .../analysis`) — без side-effects.

## Data model

`MoodEntry`, `entry_emotions`, `entry_activities`, `EntryMessage`, `AnalysisResult`, `AdviceSection` — см. [03-data-model.md](../../03-data-model.md).

## LLM-промты (дословно, версионируются в `app/llm/prompts/v1.py`, `PROMPT_VERSION`)

**Follow-up (LLM#1):**
```
Take into account that the person feels <emotions>. Ask a follow-up question about this user's message and show empathy up to 30 words long. User message <text>
```

**Анализ (LLM#2):**
```
Take into account that the person feels <emotions>. The user also wrote the following <text>. Please give me a three-part answer. In the first part, write a general title based on the information you received about the problem up to 3 words long. In the second part, provide an overview of up to 40 words. And in the third part, give advice on how to improve your well-being in this situation. The advice should be divided into sections. Answer in the language I'm asking you about the problem.
```

Подстановки:
- `<emotions>` — метки выбранных эмоций через запятую.
- `<text>` для follow-up — текст описания (`user_description`).
- `<text>` для анализа — описание + ответ на follow-up (`user_followup_answer`).

Структура ответа анализа (json_schema strict): `{ title (≤3 слова), overview (≤40 слов), advice: [{ heading, body }] }`. **Обработка нарушения лимитов длины (ADR-005, Вариант A):** валидация после генерации → при нарушении 1 retry → если всё ещё превышено, **мягкий обрез** `title`/`overview` по словам до лимита и **успешный finish** (`200`). Превышение длины **не** даёт `502`; `502 llm_upstream_error` — только реальные сбои провайдера (ошибка API / невалидный JSON). Обрез логируется (`analysis_length_truncated`).

LLM settings (env): `OPENAI_TEXT_MODEL`, `OPENAI_TRANSCRIBE_MODEL=whisper-1`, `OPENAI_TEMPERATURE`, `OPENAI_TIMEOUT_SECONDS` (~30), `LLM_MAX_RETRIES=1`.

## RBAC

Все entry-операции — строго по `device-id`. Чужой entry → `404`.

## Правила переходов и валидации (единое поведение)

- `POST /entries`: `mood` (required 1..5), `emotions` (required, может быть `[]`), `activities` (optional), `description` (required, непустой, ≤ ~4000 симв.) приходят одним телом. Сервер валидирует, вызывает LLM#1, создаёт запись сразу в `awaiting_answer`. При ошибке LLM#1 (`502/503`) запись **не создаётся**.
- `POST /entries/{id}/finish`: `answer` (required, непустой), допустим **только** из `awaiting_answer`. Иной статус → `409 entry_invalid_transition` (`details.current_status`); уже `finished` → `409 entry_already_finished`.
- Эмоции должны соответствовать уровню настроения (`Emotion.scale_level_id` == выбранный `mood`); иначе `422`. Пустой `emotions: []` валиден.
- `source` в `description` (тело `POST /entries`) и `answer` (тело `POST /finish`) — optional, дефолт `text`.
- `detected_language` из `/transcriptions` — ISO 639-1; используется как fallback для языка записи только при отсутствии явного `language`/`Accept-Language`. Язык фиксируется в момент `POST /entries` и используется обоими LLM-вызовами.

## Управление соединением при LLM-вызовах (ADR-008)

`POST /entries` (LLM#1) и `POST /finish` (LLM#2) построены по **трёхфазному паттерну**, чтобы не удерживать DB-соединение во время сетевого вызова OpenAI:

1. **Фаза 1** — короткая read-only tx: валидация по каталогу / чтение записи + status-guard, сбор данных для промта; соединение возвращается в пул.
2. **Фаза 2** — вызов LLM **без удержания соединения** (`pool.checkedout()==0` относительно запроса во время вызова).
3. **Фаза 3** — короткая write-tx: атомарная запись результата.
   - `POST /entries`: создание `MoodEntry(awaiting_answer)` + сообщения + upsert `Device`. Только при успехе LLM#1.
   - `POST /finish`: `SELECT ... FOR UPDATE OF mood_entries` (повторный status-guard) + `SELECT ... FOR UPDATE` строки `Device` (сериализация points+streak) + запись результата.

`FOR UPDATE` — реальная блокировка строки на PostgreSQL, no-op на SQLite (приемлемо для local/CI). Принятое решение, блокировка `Device` (фикс streak/points-гонки) и pool sizing — [ADR-008](../../adr/ADR-008-llm-connection-management.md), [07-deployment.md](../../07-deployment.md).

## Транзакционность finish

`POST /finish` — фаза 3 атомарна: `EntryMessage(user_followup_answer)`, `status→finished`, `AnalysisResult`+`AdviceSection`, начисление очков+streak (вызов gamification), `finished_at` — в одной транзакции под `SELECT ... FOR UPDATE` на строках `MoodEntry` **и** `Device`. Идемпотентно: повторный status-guard в фазе 3 → повторный finish finished-записи → `409`.

## DoD

- `POST /entries` создаёт `awaiting_answer` + follow-up; `POST /finish` из `awaiting_answer` → `finished`. Иной статус для finish → `409 entry_invalid_transition` (`details.current_status`); повторный finish → `409 entry_already_finished`.
- LLM-ошибки/таймаут → `502/503`; на `POST /entries` запись не создаётся, на `POST /finish` статус не меняется (шаг повторяем с тем же телом).
- `/transcriptions`: лимит 10 MB (`413`), MIME+сигнатура (`415`), аудио не сохраняется.
- Анализ парсится из Structured Outputs; лимиты длины enforced через retry → мягкий обрез (finish успешен, не `502`).
- История: cursor-пагинация по `finished_at DESC`.

## Open questions

- [Q-ENTRY-1](../../99-open-questions.md#q-entry-1) — follow-up обязателен; **структурно гарантировано** 2-POST дизайном.
- [Q-ENTRY-2](../../99-open-questions.md#q-entry-2) — ровно один follow-up; **структурно гарантировано** 2-POST дизайном.
- [Q-ENTRY-3](../../99-open-questions.md#q-entry-3) — незавершённые записи (`awaiting_answer`, не финализированы) вне scope MVP (не удаляются/не листятся клиентом); промежуточного серверного сохранения выбора до `POST /entries` нет.
- [Q-SEC-1](../../99-open-questions.md#q-sec-1) — аудио не хранить (дефолт).
- [Q-LLM-1](../../99-open-questions.md#q-llm-1) — **resolved**: prod-дефолт `OPENAI_TEXT_MODEL=gpt-4o` (Structured Outputs strict).

## Changelog

- bootstrap: спроектирован модуль.
- iter 1: backend реализовал Phase 2–6 (lifecycle, STT, follow-up, анализ, история). Зафиксированы решения: ADR-005 Вариант A (нарушение лимитов длины → retry → мягкий обрез → success, **требует rework кода**); автодетект языка по тексту скрипт-эвристикой на LLM-шаге (ADR-006).
- iter 3: `followup`/`finish` переписаны на трёхфазный паттерн управления соединением (ADR-008) — соединение не удерживается во время LLM, фаза 3 под `SELECT ... FOR UPDATE`. Устранён holistic-major #2 (scalability). Q-LLM-1 resolved: prod-модель `gpt-4o`.
- iter 4: **lifecycle упрощён до 2 POST** (ADR-003 пересмотрен): `POST /entries` (создание + LLM#1) → `awaiting_answer` → `POST /finish` (ответ + LLM#2) → `finished`. Убраны `PATCH /mood`, `PATCH /activities`, `POST /description`, `POST /followup`, `POST /followup/answer` и промежуточные статусы. `POST /entries` теперь тоже трёхфазный (LLM#1). Добавлен `FOR UPDATE` строки `Device` в фазе 3 finish (фикс streak/points-гонки, ADR-008). **Требует rework backend** (переписать lifecycle).
