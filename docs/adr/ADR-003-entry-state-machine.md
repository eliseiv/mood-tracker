# ADR-003 — Entry как двухшаговый ресурс (2 POST по числу ответов ИИ)

Status: accepted
Дата создания: bootstrap; пересмотрено iteration 4 (упрощение до 2 POST).

## Context

Запись настроения концептуально собирается из: настроение → эмоции → активности → описание → follow-up ИИ → ответ пользователя → финальный анализ. ИИ участвует дважды: эмпатичный follow-up (LLM#1) и финальный анализ (LLM#2).

Первоначальный дизайн (bootstrap) разбивал это на 7 серверных шагов с промежуточными статусами (`draft → mood_set → activities_set → described → followup_pending → followup_answered → finished`) и отдельными вызовами `PATCH /mood`, `PATCH /activities`, `POST /description`, `POST /followup`, `POST /followup/answer`, `POST /finish`. На практике клиент (iOS) собирает весь выбор настроения/эмоций/активностей/описания в одном экране и отправляет одновременно; промежуточное серверное сохранение выбора до отправки не требуется (согласуется с [Q-ENTRY-3](../99-open-questions.md#q-entry-3) — незавершённые записи клиентом не управляются). Множество endpoint'ов и статусов усложняло и контракт для iOS, и серверную state machine, не давая ценности.

## Decision

Lifecycle упрощён до **двух POST — по числу ответов ИИ**:

```
[*] --POST /entries--> awaiting_answer --POST /entries/{id}/finish--> finished
```

- **`POST /entries`** (создание + LLM#1): тело `{ mood (required 1..5), emotions (required, must match mood level), activities (optional), description (required, non-empty), source, language, timezone }`. Сервер валидирует, синхронно вызывает LLM#1 (эмпатичный follow-up, дословный промт v1), и в одной транзакции создаёт запись сразу в статусе `awaiting_answer` с сообщениями `user_description` + `ai_followup`, upsert `Device.timezone`/`locale`. → `201 { entry_id, status, question, prompt_version }`.
- **`POST /entries/{id}/finish`** (ответ + LLM#2): тело `{ answer (required, non-empty), source }`. Допустим только из `awaiting_answer`. Сохраняет `user_followup_answer`, синхронно вызывает LLM#2 (анализ через Structured Outputs, truncate по ADR-005 Вариант A), атомарно создаёт `AnalysisResult`+`AdviceSection`, начисляет `POINTS_PER_ENTRY` и обновляет streak, → `finished`. → `200 { analysis, reward, streak }`.

Статусы: только `awaiting_answer` и `finished` (`draft` не нужен — описание приходит сразу в `POST /entries`). Нарушения:
- `POST /finish` из статуса ≠ `awaiting_answer` → `409 entry_invalid_transition` с `details.current_status`.
- Повторный `POST /finish` на `finished` → `409 entry_already_finished`.

Оба POST синхронно вызывают LLM и используют трёхфазное управление соединением ([ADR-008](ADR-008-llm-connection-management.md)): при ошибке LLM запись не создаётся / не финализируется, шаг безопасно повторяется. Детали контракта — [04-api-contract.md](../04-api-contract.md), модуль — [modules/entries](../modules/entries/README.md).

## Consequences

- (+) Минимальный контракт для iOS: два вызова по числу ответов ИИ, очевидная state machine из двух статусов.
- (+) Меньше endpoint'ов, статусов и пограничных переходов → меньше серверной валидации и тестовых веток.
- (+) Структурно гарантирует «ровно один follow-up перед finish» ([Q-ENTRY-1](../99-open-questions.md#q-entry-1), [Q-ENTRY-2](../99-open-questions.md#q-entry-2)) без отдельной проверки.
- (−) Нет промежуточного серверного сохранения выбора настроения/активностей до отправки: если пользователь бросил экран до `POST /entries`, на сервере ничего нет. Приемлемо и согласуется с [Q-ENTRY-3](../99-open-questions.md#q-entry-3) (клиент не управляет незавершёнными записями).
- (−) `POST /entries` стал «тяжёлым» (валидация + LLM#1 в одном вызове) — компенсируется трёхфазным паттерном (ADR-008) и rate limit.

## Alternatives

- **7 серверных шагов с промежуточными статусами** (исходный дизайн bootstrap) — отклонён как избыточный: промежуточные сохранения не нужны, усложняли контракт и state machine.
- **Один POST на всю запись** (mood+description+answer сразу) — отклонён: follow-up ИИ зависит от описания, поэтому ответ пользователя физически не может прийти в том же запросе. Два POST = минимум, диктуемый двумя ответами ИИ.
