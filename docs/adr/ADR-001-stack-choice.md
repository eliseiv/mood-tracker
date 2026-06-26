# ADR-001 — Технологический стек

Status: accepted

## Context

Backend для iOS-приложения «Mood Tracker». Нужен async-friendly стек (синхронные вызовы OpenAI GPT/Whisper, БД), быстрый старт, малая команда (1–2 разработчика). Решение утверждено пользователем.

## Decision

- **Python 3.12** + **FastAPI** (^0.115), **uvicorn** (uvloop в prod).
- **SQLAlchemy 2.x async** + **Alembic** для миграций.
- **Pydantic v2** + **pydantic-settings** для схем и конфига.
- **openai** Async SDK для GPT и Whisper.
- **PostgreSQL 16** в prod (JSONB, UUID), **SQLite** локально (aiosqlite).
- Зависимости — **uv** + `pyproject.toml`.
- Команды и версии зафиксированы в [02-tech-stack.md](../02-tech-stack.md).

## Consequences

- (+) Единый async-стек, зрелая экосистема, простой деплой монолита.
- (+) SQLite ускоряет локальную разработку и тесты.
- (−) Различия SQLite/Postgres (JSONB, функциональные индексы) требуют внимания в моделях/миграциях.
- (−) Синхронные LLM-вызовы создают латентность на followup/finish — митигируется таймаутами и rate limit.

## Alternatives

- Node/NestJS, Go — отклонены: команда продуктивнее на Python, OpenAI SDK first-class.
- Сразу только Postgres без SQLite — отклонено: усложняет локальный onboarding.
