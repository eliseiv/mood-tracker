# ADR Index

Реестр архитектурных решений. Статус: `accepted` | `superseded` | `deprecated`.

| ADR | Решение | Статус |
|---|---|---|
| [ADR-001](ADR-001-stack-choice.md) | Технологический стек | accepted |
| [ADR-002](ADR-002-monolith.md) | Монолитная архитектура | accepted |
| [ADR-003](ADR-003-entry-state-machine.md) | Entry как двухшаговый ресурс (2 POST по числу ответов ИИ) | accepted |
| [ADR-004](ADR-004-stateless-transcription.md) | Транскрипция — отдельный stateless endpoint | accepted |
| [ADR-005](ADR-005-structured-llm-output.md) | Structured Outputs для анализа LLM | accepted |
| [ADR-006](ADR-006-language-handling.md) | Язык ответа задаётся клиентом | accepted |
| [ADR-007](ADR-007-device-id-identity.md) | Анонимная идентификация по device-id (опаковая строка, не только UUID) | accepted |
| [ADR-008](ADR-008-llm-connection-management.md) | Трёхфазное управление DB-соединением при синхронных LLM-вызовах | accepted |
| [ADR-009](ADR-009-app-level-api-key.md) | App-level аутентификация по статическому API-ключу (`X-API-Key`) | accepted |
| [ADR-010](ADR-010-catalog-localization.md) | Локализация каталога (EN+RU) явными колонками `label_en`/`label_ru` | accepted |
