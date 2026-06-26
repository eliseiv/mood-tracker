# ADR-004 — Транскрипция как отдельный stateless endpoint

Status: accepted

## Context

iOS отправляет аудио на backend для распознавания речи (Whisper). Результат (`text`) клиент использует как `description` в `POST /entries` или как `answer` в `POST /finish`. STT не обязан быть привязан к конкретной записи в момент распознавания.

## Decision

Отдельный stateless endpoint `POST /transcriptions` (multipart, поле `audio`) → `{ text, detected_language }`. Не привязан к entry, ничего не сохраняет в БД, аудио не хранится (см. ADR/Q-SEC-1). Строгий rate limit. MIME allow-list + magic-bytes, лимит 10 MB.

## Consequences

- (+) Простая, переиспользуемая операция; клиент сам решает, куда вставить текст.
- (+) Изоляция дорогого/опасного приёма файлов от entry-логики.
- (−) Клиент делает дополнительный вызов перед `POST /entries` (description) / `POST /finish` (answer) — приемлемо.

## Alternatives

- Приём аудио прямо в `POST /entries`/`POST /finish` — отклонено: смешивает stateful entry-логику с файловой загрузкой и усложняет валидацию/лимиты.
