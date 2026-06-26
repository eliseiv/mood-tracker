# 07 — Deployment

## Окружения

| Окружение | `APP_ENV` | БД | Rate limit | App-key (`API_KEY`) | Назначение |
|---|---|---|---|---|---|
| local | `local` (default) | SQLite (aiosqlite) | in-memory | опционален (пусто → барьер выключен) | разработка/тесты |
| prod (single-instance) | `prod` | PostgreSQL 16 | in-memory (`memory`) — допустимо при 1 реплике | **обязателен** (непустой; иначе отказ старта) | боевое (текущий деплой) |
| prod (multi-replica) | `prod` | PostgreSQL 16 | **Redis** (`redis` + `REDIS_URL`) — обязателен при >1 реплике | **обязателен** | боевое при горизонтальном масштабировании |

> **Текущий деплой — single-instance** (одна реплика api за Traefik): `RATE_LIMIT_BACKEND=memory` — осознанный выбор, см. «Rate limiting backend» ниже.

## Артефакт

- Docker-образ на базе `python:3.12-slim`. Зависимости через `uv sync --frozen --extra prod` (prod-драйверы `asyncpg` + `redis` вынесены в optional extra `[prod]`; локально/CI без БД — `uv sync`). Обоснование группировки — [02-tech-stack.md](02-tech-stack.md).
- `tzdata` входит в основные зависимости — IANA tz-база нужна для `zoneinfo` (streak) в slim-образе.
- Запуск: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (uvloop в prod).
- Non-root пользователь в контейнере.

## Текущий prod-деплой (факт)

Сервис развёрнут на общем сервере (devops):

| Параметр | Значение |
|---|---|
| Домен | `moodaitracker.shop` |
| Reverse-proxy / TLS | Traefik (TLS-терминация, маршрутизация) |
| Топология api | **single-instance** (одна реплика контейнера) |
| БД | PostgreSQL (один инстанс) |
| Redis | **не разворачивается** (исключён из ТЗ деплоя; не нужен при 1 реплике) |
| `APP_ENV` | `prod` |
| `API_KEY` | задан непустым (prod-guard проходит) |
| `RATE_LIMIT_BACKEND` | `memory` (in-memory; корректно при 1 реплике — см. «Rate limiting backend») |
| `TRUST_PROXY_HEADERS` | `true` (за Traefik; прокси перезаписывает `X-Forwarded-For`) |
| `OPENAI_TEXT_MODEL` | `gpt-4o` |

> При переходе на >1 реплику api необходимо добавить Redis и переключить `RATE_LIMIT_BACKEND=redis` ([Q-RATE-1](99-open-questions.md#q-rate-1)).

## Конфигурация

- Все настройки — через env (см. [05-security.md](05-security.md)). Секреты — через secret manager платформы, не в образе.
- **Секреты** (через secret manager, не в коде/образе/логах): `OPENAI_API_KEY`, **`API_KEY`** (app-level `X-API-Key`, ADR-009), `DATABASE_URL`. `API_KEY` должен совпадать с ключом, прошитым в iOS-сборку; смена ключа = синхронное обновление сервера и клиента (ротация без простоя — [Q-AUTH-1](99-open-questions.md#q-auth-1)).
- `.env.example` — шаблон без значений (включая `API_KEY=`, `APP_ENV=local`).
- **LLM-модель**: prod-дефолт `OPENAI_TEXT_MODEL=gpt-4o` (поддерживает Structured Outputs `json_schema` strict, Q-LLM-1 resolved). `OPENAI_TRANSCRIBE_MODEL=whisper-1`.

### App-key barrier: prod-guard (fail-closed, ADR-009)

- Проверка `X-API-Key` enforced **тогда и только тогда, когда `API_KEY` непустой**. Пустой `API_KEY` выключает барьер — допустимо **только** при `APP_ENV=local` (разработка/тесты).
- **prod обязан задать непустой `API_KEY`.** При `APP_ENV=prod` и пустом `API_KEY` приложение **отказывается стартовать** (явная ошибка конфигурации) — это намеренный fail-closed против тихого открытого доступа. Деплой должен задавать `APP_ENV=prod`.
- Deployment checklist ниже — defense-in-depth поверх guard, не вместо него.

### Rate limiting backend: memory vs redis

- **`RATE_LIMIT_BACKEND=memory` (in-memory) допустим и осознанно выбран для текущего single-instance деплоя.** Счётчики лимитера (по `device-id` и IP) живут в процессе одной реплики api; при **одной** реплике этого достаточно и корректно. Нет внешней зависимости Redis для MVP.
- **`RATE_LIMIT_BACKEND=redis` (+ `REDIS_URL`) становится ОБЯЗАТЕЛЕН при масштабировании api на >1 реплику.** С несколькими репликами in-memory счётчики не разделяются между процессами → лимиты можно обойти распределением запросов по репликам; общий стор (Redis) делает лимиты глобальными.
- Переход на Redis при росте нагрузки/горизонтальном масштабировании — [Q-RATE-1](99-open-questions.md#q-rate-1). Это **условие масштабирования**, а не дефект текущего деплоя.

### CORS — формат `CORS_ALLOW_ORIGINS`

Значение `CORS_ALLOW_ORIGINS` принимается в трёх формах (пустое значение больше не ломает старт — исправлен парсинг):

| Форма | Пример | Результат |
|---|---|---|
| пусто | `CORS_ALLOW_ORIGINS=` | `[]` — cross-origin не разрешён (по умолчанию) |
| comma-separated | `CORS_ALLOW_ORIGINS=https://a.app,https://b.app` | `["https://a.app","https://b.app"]` |
| JSON-массив | `CORS_ALLOW_ORIGINS=["https://a.app"]` | `["https://a.app"]` |

- Дефолт (переменная не задана/пуста) → `[]`. В prod указывать явный список origin'ов; **не** `*` (см. [05-security.md](05-security.md)). Для нативного iOS-клиента CORS обычно не требуется → `[]` приемлемо.

## Прокси и источник IP (rate limiting)

- **prod за load balancer / reverse-proxy**: выставить `TRUST_PROXY_HEADERS=true`. Источник IP лимитера тогда — первый адрес `X-Forwarded-For`.
- **Требование к инфраструктуре**: доверенный прокси/LB **обязан перезаписывать** `X-Forwarded-For` (ставить реальный client-IP первым элементом), а не дополнять клиентским значением. Иначе клиент сможет подменить IP и обойти лимитер.
- **Без прокси** (прямые соединения): `TRUST_PROXY_HEADERS=false` (default) — IP берётся из адреса соединения. Модель доверия — [05-security.md §Источник IP и доверенный прокси](05-security.md).

## DB connection pool (синхронные LLM-вызовы)

- `POST /entries` (LLM#1) и `POST /entries/{id}/finish` (LLM#2) используют трёхфазный паттерн (короткая read-only tx → release соединения → LLM без соединения → короткая write-tx): соединение из пула **не удерживается** во время сетевого вызова OpenAI. Детали — [01-architecture.md](01-architecture.md), [ADR-008](adr/ADR-008-llm-connection-management.md).
- **Сериализация finish**: фаза 3 finish делает `SELECT ... FOR UPDATE OF mood_entries` (повторный status-guard) + `SELECT ... FOR UPDATE` строки `Device` (сериализация points/streak). На **PostgreSQL** это реальная блокировка строк (защита от гонок параллельного finish одной записи и lost-update streak/points при finish разных записей одного устройства); на **SQLite** `FOR UPDATE` — no-op (приемлемо для local/CI, где конкуренция отсутствует).
- **Pool sizing**: поскольку соединение не занято на время LLM, размер пула рассчитывается по короткими tx, а не по длительности LLM. Рекомендация: `pool_size` ≈ числу воркеров/конкурентных коротких запросов; перегрузка пула не масштабируется с `OPENAI_TIMEOUT_SECONDS`.
- **Timeout**: `OPENAI_TIMEOUT_SECONDS` (~30) ограничивает сетевой вызов и не влияет на удержание соединения. `pool_timeout` (ожидание свободного соединения) держать существенно ниже суммарного времени запроса; превышение → быстрый отказ вместо накопления очереди.

## Миграции

- Alembic. На деплое: `alembic upgrade head` перед стартом приложения (отдельный шаг/init-контейнер).
- Seed каталога: `python -m app.seed.catalog_seed` (идемпотентно) — после миграций. Сеет built-in baseline-каталог уровней/эмоций/активностей (placeholder-набор приемлем; Q-CATALOG-1 resolved-by-design). Кастомные активности расширяются клиентом через `POST /activities`.

## Prod deployment checklist (defense-in-depth)

Перед prod-деплоем подтвердить (guard на старте — основная защита, чеклист — дополнительная):

- [ ] `APP_ENV=prod` задан.
- [ ] `API_KEY` задан непустым (через secret manager) и совпадает с ключом iOS-сборки. *(Если пуст — приложение не стартует: prod-guard ADR-009.)*
- [ ] `OPENAI_API_KEY`, `DATABASE_URL` заданы (secret manager).
- [ ] **Rate limit backend по числу реплик:** single-instance (1 реплика) → `RATE_LIMIT_BACKEND=memory` допустим; **multi-replica (>1 реплики) → `RATE_LIMIT_BACKEND=redis` + `REDIS_URL` обязательны** (см. «Rate limiting backend», [Q-RATE-1](99-open-questions.md#q-rate-1)).
- [ ] `TRUST_PROXY_HEADERS=true` если за reverse-proxy/LB (Traefik) — прокси перезаписывает `X-Forwarded-For`.
- [ ] `CORS_ALLOW_ORIGINS` — явный список или пусто (`[]`); не `*`.
- [ ] `OPENAI_TEXT_MODEL=gpt-4o`.

## Health checks

- `GET /health` → liveness/readiness. Без БД-проверки на liveness; readiness может проверять доступность БД. **`/health` не требует `X-API-Key`/`X-Device-Id`** — пригоден для проб инфраструктуры.

## CI/CD (требования к pipeline — настраивает devops)

1. `uv sync` (lint/type/test-стадии); `uv sync --extra prod` для build/deploy-стадий с prod-драйверами
2. `ruff check .` + `ruff format --check .`
3. `mypy app`
4. `pytest --cov=app --cov-fail-under=80`
5. build Docker image
6. (prod) `alembic upgrade head` → deploy → smoke `GET /health`

## Rollback

- **Версионирование образа по commit SHA.** CI собирает и тегирует образ `moodtracker-api:${IMAGE_TAG}`, где `IMAGE_TAG=<git-sha>` (`docker-compose.yml`, `.github/workflows/deploy.yml`). Предыдущие SHA-образы остаются на сервере → rollback = передеплой предыдущего тега без пересборки.
- **Что сохраняется при rollback:** `.env` (секреты, не в git) и том `pgdata` (БД) переживают передеплой — пересоздаётся только контейнер `api`.

### Процедура отката (на сервере, в `/opt/moodtracker`)

Откат на предыдущий релиз (без пересборки, если образ ещё на сервере):

```bash
cd /opt/moodtracker
docker image ls moodtracker-api            # найти предыдущий <prev_sha> тег
git checkout --force <prev_sha>            # код под этот образ (compose/labels)
IMAGE_TAG=<prev_sha> docker compose up -d  # поднять прежний образ; .env/pgdata целы
docker compose ps && curl --fail -sS https://moodaitracker.shop/health
```

Если образа предыдущего тега на сервере нет (запрунен) — пересобрать из кода:
`git checkout --force <prev_sha> && IMAGE_TAG=<prev_sha> docker compose up -d --build`.

- **Миграции** пишутся обратимо где возможно; деструктивные изменения — в отдельных шагах. Откат образа на прежний SHA **не** откатывает применённые миграции автоматически — схема БД остаётся на `head`. Часто это безопасно (прежний код совместим с новой схемой при backward-compatible миграциях). При **несовместимой** схеме `alembic downgrade <rev>` выполняется **осознанно и вручную** — деструктивный downgrade может привести к потере данных; сначала downgrade, затем передеплой прежнего образа.
- **Smoke после отката** обязателен: `GET /health` → 200 (как в CI-job `smoke`).

## Observability

- Структурные логи (без секретов/текста сообщений, см. 05-security).
- Метрики: latency LLM-вызовов, частота `429/502/503`, число finished entries.
