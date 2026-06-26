# Module: identity

Status: in-progress

Анонимная идентификация устройства и профиль.

## Scope

- Middleware аутентификации/идентификации, **порядок**: (1) `X-API-Key` — app-level статический ключ, constant-time сравнение с env `API_KEY`, отсутствует/неверный → `401 api_key_required`/`api_key_invalid` (ADR-009); (2) `X-Device-Id` — **опаковая строка** (trim → непустой, ≤64, `^[A-Za-z0-9._-]+$`), пусто → `400 device_id_required`, нарушение → `400 device_id_invalid`; upsert `Device`, скоуп (ADR-007). `GET /health` — без обоих заголовков.
- **device-id (ADR-007):** хранится как `String(64)` как есть (echo в `GET /me`), не маппится в UUID, регистрозависим. UUID — валидный частный случай.
- **Семантика включения app-key (ADR-009):** барьер enforced при непустом `API_KEY`; пустой → проверка пропускается (только local/dev/test). **Prod-guard:** при `APP_ENV=prod` и пустом `API_KEY` приложение **отказывается стартовать** (fail-closed); при `APP_ENV=local` пустой ключ допустим (лог-предупреждение).
- Профиль: `GET /me`, `GET /me/streak`, `GET /me/points`, `DELETE /me`.
- Хранение `Device.timezone` (IANA) и `Device.locale` (язык): upsert из полей `timezone`/`language` запроса `POST /entries` (last-write-wins). Невалидная зона игнорируется. `timezone` нужен gamification для streak по локальной дате (Q-GAME-2); при `null` — UTC.

## Out of scope

- Логин, аккаунты, кросс-девайс синхронизация.
- Логика streak/points (модуль gamification; identity только отдаёт значения).

## API

См. [04-api-contract.md §6.1](../../04-api-contract.md). Endpoints: `GET /me`, `GET /me/streak`, `GET /me/points`, `DELETE /me`.

## Data model

`Device` — см. [03-data-model.md](../../03-data-model.md).

## RBAC

Доступ только к собственному `Device` (по заголовку). Чужого `Device` концептуально нет — id и есть ключ.

## Dependencies

Базовый модуль; от него зависят все остальные (скоуп по `device-id`).

## DoD

- Middleware проверяет `X-API-Key` **первым**: нет → `401 api_key_required`, неверный → `401 api_key_invalid` (constant-time, без раскрытия деталей, не логируется); затем `X-Device-Id`: пусто/только пробелы → `400 device_id_required`, длина >64 или символы вне `[A-Za-z0-9._-]` → `400 device_id_invalid`. `testuser` и UUID — оба валидны. `/health` работает без обоих.
- `GET /me` возвращает `device_id` ровно как прислан (echo, без маппинга в UUID).
- Запрос без/с неверным `X-API-Key` отклоняется до upsert `Device` (нелегитимный запрос не создаёт устройство).
- При непустом `API_KEY` барьер enforced; при `APP_ENV=prod` + пустой `API_KEY` старт приложения завершается ошибкой конфигурации (prod-guard, ADR-009).
- Upsert идемпотентен, `last_seen_at` обновляется.
- `timezone`/`locale` обновляются при передаче в `POST /entries`; невалидный `timezone` не перезаписывает сохранённый.
- `DELETE /me` каскадно удаляет все связанные данные (Q-DATA-1).

## Open questions

- [Q-ID-1](../../99-open-questions.md#q-id-1) — переустановка = новый device-id (дефолт принят); device-id — опаковая строка (ADR-007).
- [Q-DATA-1](../../99-open-questions.md#q-data-1) — `DELETE /me` добавлен.
- [Q-AUTH-1](../../99-open-questions.md#q-auth-1) — ротация app-key (один статический ключ в MVP, ADR-009).

## Changelog

- bootstrap: спроектирован модуль.
- iter 1: backend реализовал middleware + профиль. Добавлен механизм установки `Device.timezone` через поле `timezone` (Q-GAME-2).
- iter 2: backend реализовал приём поля `timezone` и upsert `Device.timezone`/`locale` (закрытие rework по Q-GAME-2).
- iter 4: источник upsert `timezone`/`locale` — только `POST /entries` (2-POST lifecycle, ADR-003; `PATCH /mood` удалён).
- iter 5: добавлена app-level аутентификация `X-API-Key` (ADR-009) — проверяется в middleware **до** `X-Device-Id`; constant-time, `401 api_key_required`/`api_key_invalid`.
- iter 6: backend реализовал `X-API-Key` (barrier enforced при непустом `API_KEY`; пустой → выключен для local/test). Зафиксирована семантика и **prod-guard** (ADR-009): `APP_ENV=prod` + пустой `API_KEY` → отказ старта. **Требует rework backend** — добавить env `APP_ENV` и стартовый guard (fail-closed).
- iter 8: `X-Device-Id` → **опаковая строка** (ADR-007 пересмотрен): валидация UUID заменена на (непустой, ≤64, `[A-Za-z0-9._-]`); `Device.id` и FK → `String(64)`; echo как есть. **Требует rework backend** (валидация + миграция UUID→String(64), [03-data-model.md](../../03-data-model.md)).
