# 05 — Security

## App-level аутентификация (`X-API-Key`, ADR-009)

- Заголовок `X-API-Key` — **статический общий секрет приложения** (один на все инсталляции). Аутентифицирует приложение, отсекая публичный доступ/абьюз поверх per-device rate limit. Это барьер уровня приложения, **не** замена анонимной идентификации устройства.
- Обязателен на всех `/api/v1/*`. Исключение — `GET /health` (без `X-API-Key` и без `X-Device-Id`).
- **Порядок проверки в middleware: сначала `X-API-Key`, затем `X-Device-Id`.** Запрос без/с неверным ключом → `401` **до** валидации device-id и до upsert `Device` (ранний отказ, не создаёт `Device` для нелегитимных запросов).
- Коды: отсутствует → `401 api_key_required`; неверный → `401 api_key_invalid`. `401` без раскрытия деталей (не сообщать, чем именно ключ неверен).
- **Сравнение constant-time** (`secrets.compare_digest` или эквивалент) — защита от timing-атак. Ключ **не логируется** (наравне с device-id/секретами).
- Секрет — в env `API_KEY` (см. ниже «Секреты»). Один статический ключ — осознанное упрощение MVP; ротация/набор per-client ключей — расширение ([Q-AUTH-1](99-open-questions.md#q-auth-1)).
- **Семантика включения барьера (ADR-009):** проверка `X-API-Key` enforced **тогда и только тогда, когда `API_KEY` непустой**. Пустой `API_KEY` → барьер выключен — допустимо **только** для local/dev/test.
  - **PROD:** `API_KEY` **обязателен** (непустой). Отсутствие = ошибка конфигурации, не «открытый доступ».
  - **Prod-guard (fail-closed):** при `APP_ENV=prod` и пустом `API_KEY` приложение **отказывается стартовать** (явная ошибка на старте), исключая тихий fail-open. При `APP_ENV=local` пустой ключ допустим (барьер выключен, лог-предупреждение). Deployment checklist — defense-in-depth поверх guard ([07-deployment.md](07-deployment.md)).

## Идентификация и авторизация (устройство)

- Анонимная идентификация по заголовку `X-Device-Id` (UUID v4) — ADR-007. Проверяется **после** `X-API-Key`.
- Middleware: валидация формата UUID → upsert `Device` → проброс `device_id` в request scope. Невалидный/отсутствующий (кроме `/health`) → `400`.
- Авторизация = скоуп по `device-id`. Любой ресурс фильтруется по `device_id`. Доступ к чужому ресурсу → `404` (не `403`), чтобы не раскрывать существование.
- Пользовательского логина/паролей/аккаунтов/сессионных токенов нет; `X-API-Key` — секрет приложения, а не пользователя.

## Секреты

- `OPENAI_API_KEY`, `API_KEY` (app-level ключ) и строка подключения к БД — только из env / secret manager. Никогда в коде/репозитории/логах.
- `.env.example` содержит имена переменных без значений (включая `API_KEY=`).
- Логи не содержат секретов (в т.ч. `X-API-Key`).

## Конфигурация (env)

| Переменная | Назначение |
|---|---|
| `APP_ENV` | среда выполнения: `local` \| `prod` (default `local`). При `prod` пустой `API_KEY` → отказ старта (ADR-009 prod-guard) |
| `DATABASE_URL` | подключение к БД |
| `API_KEY` | app-level статический ключ (`X-API-Key`); секрет, constant-time. Barrier enforced при непустом значении; пустой → выключен (только local). В prod обязателен (ADR-009) |
| `OPENAI_API_KEY` | ключ OpenAI |
| `OPENAI_TEXT_MODEL` | id GPT-модели; prod-дефолт `gpt-4o` (Q-LLM-1 resolved) |
| `OPENAI_TRANSCRIBE_MODEL` | `whisper-1` |
| `OPENAI_TEMPERATURE` | температура генерации |
| `OPENAI_TIMEOUT_SECONDS` | таймаут LLM (~30) |
| `LLM_MAX_RETRIES` | 1 |
| `RATE_LIMIT_BACKEND` | `memory` (local и single-instance prod) / `redis` (обязателен при >1 реплике, Q-RATE-1) |
| `REDIS_URL` | для rate limit при `redis` (multi-replica) |
| `TRUST_PROXY_HEADERS` | доверять `X-Forwarded-For` для источника IP лимитера; default `false`, в prod за LB — `true` |
| `MAX_AUDIO_BYTES` | 10485760 (10 MB) |
| `MAX_TEXT_CHARS` | ~4000 |
| `POINTS_PER_ENTRY` | 20 (Q-GAME-1) |
| `CORS_ALLOW_ORIGINS` | осознанный список origin'ов; пусто→`[]`, comma-separated или JSON-массив (формат — [07-deployment.md](07-deployment.md)). Не `*` в prod |

## Rate limiting

- Ключи лимитера: по `device-id` **и** по IP. Для дорогих категорий (`llm` — `POST /entries` и `POST /entries/{id}/finish`, `transcription` — `POST /transcriptions`) применяются оба ключа независимо, чтобы один device-id не обходил лимит сменой id и чтобы один IP не выжигал квоту множеством device-id.
- Строже на `POST /transcriptions`, `POST /entries` (LLM#1), `POST /entries/{id}/finish` (LLM#2) — дорогие LLM/STT вызовы.
- Ответ `429` + заголовок `Retry-After` (секунды).
- Store (`RATE_LIMIT_BACKEND`): **in-memory** корректен в пределах **одного процесса/реплики** — допустим для local и для **single-instance prod** (текущий деплой). **Redis** обязателен при **>1 реплике** api (иначе счётчики не разделяются между процессами и лимит обходится распределением запросов). Условие масштабирования — [Q-RATE-1](99-open-questions.md#q-rate-1), детали — [07-deployment.md](07-deployment.md).

### Источник IP и доверенный прокси

- IP по умолчанию берётся из адреса соединения (`request.client.host`). Флаг `TRUST_PROXY_HEADERS` (`Settings.trust_proxy_headers`, **default `false`**).
- При `TRUST_PROXY_HEADERS=true` IP берётся из **первого** адреса заголовка `X-Forwarded-For` (client-IP, добавленный ближайшим доверенным прокси/LB).
- **Модель доверия:**
  - **Без прокси** (сервис принимает соединения напрямую): `TRUST_PROXY_HEADERS=false`. `X-Forwarded-For` от клиента игнорируется — иначе клиент мог бы подменить IP и обойти лимитер.
  - **За LB/reverse-proxy в prod**: `TRUST_PROXY_HEADERS=true`, но это безопасно **только если** инфраструктурный прокси/LB **перезаписывает** (а не дополняет клиентским значением) `X-Forwarded-For`. Приложение не должно доверять XFF, пришедшему напрямую от недоверенного клиента, минуя доверенный прокси.
- Деплой-инструкция — [07-deployment.md](07-deployment.md).

## Валидация загрузки аудио

- Лимит размера: `MAX_AUDIO_BYTES` (10 MB) → `413`.
- MIME allow-list по заголовку **и** по magic-bytes сигнатуре → `415`.
- Аудио не сохраняется на диск/в БД (Q-SEC-1): обрабатывается в памяти/стримом и отправляется в Whisper.

## Валидация текста

- Описание и ответы ≤ `MAX_TEXT_CHARS` (~4000) → `422`.
- Все enum/коды (mood, emotion code, activity id) валидируются против БД → `422`/`404`.

## Логирование

- Структурные логи. На уровне INFO **не логируются**: текст сообщений пользователя, содержимое аудио, ответы LLM целиком, секреты.
- Корреляция по `device-id` (хешированному при необходимости) и `entry_id`.

## Сетевые меры

- TLS verify включён для исходящих вызовов OpenAI; таймауты обязательны.
- Security headers (например `X-Content-Type-Options`, `Referrer-Policy`).
- CORS: явный список origin'ов (`CORS_ALLOW_ORIGINS`), не `*` в prod.

## Модель угроз (кратко)

| Угроза | Митигизация |
|---|---|
| Публичный доступ/абьюз вне легитимного клиента | App-level `X-API-Key` (ADR-009): обязателен на `/api/v1/*`, проверяется первым, `401` при отсутствии/неверном; constant-time сравнение |
| Timing-атака на app-key | Сравнение ключа constant-time (`secrets.compare_digest`); `401` без раскрытия деталей |
| Перебор/спуфинг device-id | Скоуп + `404` на чужое; rate limit по device-id **и** IP |
| Спуфинг IP через `X-Forwarded-For` | `TRUST_PROXY_HEADERS=false` по умолчанию; XFF доверяется только за прокси, перезаписывающим заголовок |
| Злоупотребление дорогими LLM-вызовами | Строгий rate limit на `POST /entries` / `POST /finish` / `POST /transcriptions` |
| Загрузка вредоносных/больших файлов | Лимит размера + MIME + сигнатура; аудио не хранится |
| Утечка секретов | env/secret manager; логи без секретов |
| Раскрытие чужих данных | Жёсткий скоуп по device-id |
