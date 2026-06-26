# 02 — Tech Stack

Единственное место, где фиксируется стек и команды. Остальные агенты language-agnostic и берут команды отсюда. Обоснование выбора — [ADR-001](adr/ADR-001-stack-choice.md).

## Язык и runtime

- **Python 3.12**

## Backend framework и библиотеки

| Компонент | Технология | Версия | Группа |
|---|---|---|---|
| Web framework | FastAPI | ^0.115 | core |
| ASGI server | uvicorn (uvloop в prod) | ^0.30 | core |
| ORM | SQLAlchemy (async) | ^2.0 | core |
| Миграции | Alembic | ^1.13 | core |
| Валидация/схемы | Pydantic v2 | ^2.8 | core |
| Конфиг | pydantic-settings | ^2.4 | core |
| OpenAI | openai (Async client) | ^1.40 | core |
| Multipart parser | python-multipart | ^0.0.9 | core |
| IANA tz database | tzdata | ^2024.1 | core |
| DB driver (local) | aiosqlite | ^0.20 | core |
| DB driver (prod) | asyncpg | ^0.29 | **extra `prod`** |
| Rate limit store (prod) | redis (async) | ^5.0 | **extra `prod`** |

> id GPT-модели фиксируется в env (`OPENAI_TEXT_MODEL`); prod-дефолт — **`gpt-4o`** (поддерживает Structured Outputs `json_schema` strict, [Q-LLM-1](99-open-questions.md#q-llm-1) resolved). `OPENAI_TRANSCRIBE_MODEL=whisper-1`.

### Обоснование группировки зависимостей

- **`python-multipart`** и **`tzdata`** — в `core` (основные `dependencies`), т.к. инфраструктурно обязательны: FastAPI требует `python-multipart` для парсинга `multipart/form-data` в `POST /transcriptions`; `tzdata` поставляет IANA-базу для `zoneinfo` (streak по локальной дате, Q-GAME-2) на Windows и slim-образах, где системной tz-базы нет.
- **`asyncpg`** и **`redis`** вынесены в **optional extra `[prod]`**: prod использует PostgreSQL + Redis, а локальная разработка/CI — SQLite (`aiosqlite`) + in-memory rate limiter (см. [07-deployment.md](07-deployment.md)). Дополнительно `asyncpg` не имеет готового wheel под Windows/py3.12, что ломало бы локальную установку под Windows — extra изолирует prod-драйверы от dev-окружения. Прод/CI ставят их явно: `uv sync --extra prod`.

## База данных

- **PostgreSQL 16** в prod (JSONB, UUID, частичные/функциональные индексы).
- **SQLite** локально (через aiosqlite). Различия (JSONB→JSON, функциональные индексы) учитываются в моделях/миграциях; нюансы — [03-data-model.md](03-data-model.md).

## Менеджер зависимостей

- **uv** + `pyproject.toml` (PEP 621). Lock-файл коммитится.

## Команды (источник истины для всех агентов)

| Действие | Команда |
|---|---|
| Установка зависимостей (local/dev) | `uv sync` |
| Установка зависимостей (prod/CI с asyncpg+redis) | `uv sync --extra prod` |
| Запуск dev-сервера | `uv run uvicorn app.main:app --reload` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type-check | `uv run mypy app` |
| Тесты | `uv run pytest` |
| Покрытие | `uv run pytest --cov=app --cov-report=term-missing` |
| Создать миграцию | `uv run alembic revision --autogenerate -m "<msg>"` |
| Применить миграции | `uv run alembic upgrade head` |
| Seed каталога | `uv run python -m app.seed.catalog_seed` |

## Стиль кода

- ruff (lint + format), line-length 100.
- mypy strict для `app/`.
- Все слои БД — async (SQLAlchemy 2 async, asyncpg/aiosqlite).
