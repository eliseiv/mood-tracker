# Mood Tracker Backend — Документация

Источник истины проекта. Backend-сервис для iOS-приложения «Mood Tracker» — психологический ИИ-помощник, который ведёт пользователя через запись настроения, эмоций, активностей, голосовой/текстовый рассказ, эмпатичный follow-up и финальный AI-анализ с советами; плюс геймификация (очки, streak).

## Карта документации

| Документ | Назначение |
|---|---|
| [00-vision.md](00-vision.md) | Цели продукта, NFR, ограничения |
| [01-architecture.md](01-architecture.md) | Компоненты, топология, поток данных |
| [02-tech-stack.md](02-tech-stack.md) | Стек, версии, команды lint/test/build |
| [03-data-model.md](03-data-model.md) | Модели данных, индексы, связи |
| [04-api-contract.md](04-api-contract.md) | **API-контракт для iOS-разработчика** (передаётся клиенту) |
| [05-security.md](05-security.md) | Auth, секреты, rate limiting, угрозы |
| [06-testing-strategy.md](06-testing-strategy.md) | Пирамида тестов, coverage gate |
| [07-deployment.md](07-deployment.md) | Деплой, окружения, миграции |
| [99-open-questions.md](99-open-questions.md) | Открытые вопросы Q-NNN-N |
| [100-known-tech-debt.md](100-known-tech-debt.md) | Реестр tech debt TD-NNN |
| [adr/INDEX.md](adr/INDEX.md) | Реестр архитектурных решений |

## Модули

| Модуль | Статус | Документация |
|---|---|---|
| identity | in-progress | [modules/identity](modules/identity/README.md) |
| catalog | in-progress | [modules/catalog](modules/catalog/README.md) |
| entries | in-progress | [modules/entries](modules/entries/README.md) |
| gamification | in-progress | [modules/gamification](modules/gamification/README.md) |

Статусы: `spec` (спроектирован, кода нет) → `in-progress` → `done`.

> Iteration 4: **lifecycle упрощён до 2 POST** (ADR-003 пересмотрен) — `POST /entries` (создание + LLM#1) → `awaiting_answer` → `POST /finish` (ответ + LLM#2) → `finished`. Убраны `PATCH /mood`, `PATCH /activities`, `POST /description`, `POST /followup`, `POST /followup/answer` и промежуточные статусы. Добавлен `FOR UPDATE` строки `Device` (фикс streak/points lost-update, ADR-008). Документация перепроектирована — **backend переписывает lifecycle**. Модули `in-progress` до rework + qa/review.
>
> Iteration 5: добавлена **app-level аутентификация по статическому API-ключу** `X-API-Key` (ADR-009) — обязателен на `/api/v1/*` (кроме `GET /health`), проверяется в middleware **до** `X-Device-Id`, constant-time, `401 api_key_required`/`api_key_invalid`. Env-секрет `API_KEY`.
>
> Iteration 6: backend реализовал `X-API-Key` (barrier enforced при непустом `API_KEY`; пустой → выключен для local/test) + исправил парсинг `CORS_ALLOW_ORIGINS` (пусто→`[]` / comma-separated / JSON). Зафиксированы: семантика включения барьера, **prod-guard** (`APP_ENV=prod` + пустой `API_KEY` → отказ старта, fail-closed, ADR-009) и формат CORS. **Требует rework backend**: env `APP_ENV` + стартовый prod-guard.
>
> Iteration 7: devops развернул сервис на `moodaitracker.shop` за Traefik (single-instance api + один postgres, без Redis), `APP_ENV=prod`, `TRUST_PROXY_HEADERS=true`, `gpt-4o`. Зафиксировано решение **rate limit backend**: `RATE_LIMIT_BACKEND=memory` допустим при single-instance (корректен в пределах 1 реплики); Redis обязателен только при >1 реплике ([Q-RATE-1](99-open-questions.md#q-rate-1)). docs↔деплой согласованы — rework не требуется.
>
> Iteration 9: **финальный каталог настроений/эмоций + локализация EN/RU** (ADR-010). 5 уровней (коды 3/5 → `neutral`/`awesome`) × 20 = **100 эмоций**, метки EN+RU. Модель локализации — явные колонки `label_en`/`label_ru` на `Emotion` и `MoodScaleLevel` (отвергнут JSONB). `GET /moods` локализуется: `?language=` → `Accept-Language` → `en`; `code` стабилен. Источник истины — `docs/modules/catalog/emotion_catalog.tsv` → seed. **Миграция 0005 non-destructive** (старые эмоции `is_active=false`, не удаляются — FK `entry_emotions` целы; идемпотентна по `code`; кросс-БД PG/SQLite). Q-CATALOG-1 resolved. **Требует rework backend** (catalog): модели, миграция 0005, seed, `GET /moods`.

## Фазы реализации

| Фаза | Содержание | Статус |
|---|---|---|
| Phase 0 | Skeleton (config, db, health, миграции) | implemented (iter 3) |
| Phase 1 | Identity + Catalog (+ app-key auth, ADR-009) | implemented (iter 3); app-key реализован (iter 6); **prod-guard `APP_ENV` — требует rework backend** |
| Phase 2 | Entry lifecycle (2-POST, ADR-003) | **docs redesigned (iter 4), требует rework backend** |
| Phase 3 | STT + Follow-up (LLM#1 в `POST /entries`) | **docs redesigned (iter 4), требует rework backend** |
| Phase 4 | Анализ (LLM#2 в `POST /finish`) | **docs redesigned (iter 4), требует rework backend** |
| Phase 5 | Геймификация (points + streak + Device row-lock) | **docs redesigned (iter 4), требует rework backend** |
| Phase 6 | История (cursor-пагинация) | implemented (iter 3) |
| Phase 7 | Hardening (rate limit, proxy/XFF, headers, observability) | implemented (iter 3) |

> **Holistic-major reviewer — устранены в iteration 3:**
> 1. DOCS-GAP: rate limiter — доверенный прокси / `X-Forwarded-For` (`TRUST_PROXY_HEADERS`) задокументирован в [05-security.md](05-security.md) и [07-deployment.md](07-deployment.md). Ключи лимитера по device-id **и** IP.
> 2. Scalability: LLM-эндпоинты переписаны на трёхфазный паттерн ([ADR-008](adr/ADR-008-llm-connection-management.md)) — DB-соединение не удерживается во время LLM; фаза 3 под `SELECT ... FOR UPDATE`.
>
> **Iteration 4 — редизайн (docs готовы, код — нет):**
> 1. Lifecycle = 2 POST (ADR-003): `POST /entries` (LLM#1) + `POST /finish` (LLM#2). Статусы: `awaiting_answer`, `finished`.
> 2. Streak/points race fix: `FOR UPDATE` строки `Device` в фазе 3 finish (ADR-008), без TD.
>
> **Iteration 5 — app-level auth (спроектирован):**
> 1. `X-API-Key` (ADR-009): обязателен на `/api/v1/*`, проверка первой (constant-time), `401`, env-секрет `API_KEY`. Не заменяет device-id.
>
> **Iteration 6 — app-key реализован + fail-safe (guard — rework backend):**
> 1. `X-API-Key` реализован; barrier enforced при непустом `API_KEY`, пустой → выключен (только local/test).
> 2. Prod-guard (ADR-009): `APP_ENV=prod` + пустой `API_KEY` → отказ старта (fail-closed). Требует env `APP_ENV` + стартовую проверку (rework backend).
> 3. `CORS_ALLOW_ORIGINS`: пусто→`[]`, comma-separated или JSON-массив.

## Точка входа для iOS-разработчика

Передавайте клиенту файл [04-api-contract.md](04-api-contract.md). Он самодостаточен: базовый URL, заголовки, все endpoint'ы с примерами, формат ошибок, state machine, happy-path сценарий, enum-значения.
