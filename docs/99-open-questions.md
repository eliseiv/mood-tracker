# 99 — Open Questions

Каждый вопрос имеет ID, дефолт (принятое на старте решение) и статус. Закрытие = новый ADR или фиксация решения в docs.

| ID | Вопрос | Дефолт (принят) | Статус |
|---|---|---|---|
| <a id="q-entry-1"></a>Q-ENTRY-1 | Follow-up обязателен перед finish? | Да — **структурно гарантировано** 2-POST дизайном (ADR-003): `POST /entries` всегда порождает follow-up, `POST /finish` всегда на него отвечает | resolved-by-design |
| <a id="q-entry-2"></a>Q-ENTRY-2 | Сколько follow-up на запись? | Ровно один — **структурно гарантировано** 2-POST дизайном (ADR-003): нет endpoint'а для второго follow-up | resolved-by-design |
| <a id="q-entry-3"></a>Q-ENTRY-3 | Нужно ли управление брошенными/незавершёнными записями (удаление/листинг)? | **Out of scope для MVP**: клиент не удаляет и не перечисляет незавершённые записи (`awaiting_answer`, не финализированы). `draft`-статуса больше нет (2-POST, ADR-003) — промежуточного серверного сохранения выбора до `POST /entries` нет вовсе. Незавершённые остаются на сервере; опциональная TTL-очистка — позже. Полное удаление — через `DELETE /me` | resolved-by-design |
| <a id="q-game-1"></a>Q-GAME-1 | Сколько очков за завершённую запись? | +20, константа `POINTS_PER_ENTRY` | resolved-default |
| <a id="q-game-2"></a>Q-GAME-2 | Как считать streak? Как задаётся `Device.timezone`? | По локальной дате с учётом `Device.timezone`. **Установка `timezone` (IANA): опциональное поле `timezone` в `POST /entries` (upsert, last-write-wins); дефолт/невалид → UTC.** Конкурентный finish сериализуется row-lock'ом на `Device` (ADR-008). Контракт — [04-api-contract §2, §6.4](04-api-contract.md) | resolved |
| <a id="q-sec-1"></a>Q-SEC-1 | Хранить ли аудио? | Не хранить (обработка в памяти → Whisper) | resolved-default |
| <a id="q-data-1"></a>Q-DATA-1 | Нужен ли способ удалить данные устройства? | Добавить `DELETE /me` (каскадное удаление) | resolved-default |
| <a id="q-id-1"></a>Q-ID-1 | Поведение при переустановке приложения? | Новый device-id = новый пользователь; клиент хранит id в Keychain | resolved-default |
| <a id="q-catalog-1"></a>Q-CATALOG-1 | Точный seed-список эмоций по уровням и built-in-активностей | **Решено (финальный датасет)**: каталог зафиксирован — 5 уровней (`terrible`/`bad`/`neutral`/`good`/`awesome`) + **100 эмоций** (5×20) с метками EN+RU, источник истины [modules/catalog/emotion_catalog.tsv](modules/catalog/emotion_catalog.tsv) → seed `app/seed/catalog_seed.py`. Локализация — колонки `label_en`/`label_ru` ([ADR-010](adr/ADR-010-catalog-localization.md)). Миграция каталога — [03-data-model.md §Миграция каталога](03-data-model.md). Кастомные activities — клиент через `POST /activities`. Placeholder-статус снят | resolved |
| <a id="q-llm-1"></a>Q-LLM-1 | Точные id GPT-моделей для текста | **Решено пользователем**: prod-модель текстовых вызовов — **`gpt-4o`** (поддерживает Structured Outputs `json_schema` strict). id берётся из `Settings.openai_text_model` (env `OPENAI_TEXT_MODEL`), prod-дефолт `gpt-4o`. Зафиксировано в [02-tech-stack.md](02-tech-stack.md), [07-deployment.md](07-deployment.md) | resolved |
| <a id="q-auth-1"></a>Q-AUTH-1 | Ротация app-level ключа / per-client ключи | **Дефолт (MVP)**: один статический общий ключ `API_KEY` (`X-API-Key`, ADR-009). Ротация требует синхронного обновления клиента и сервера. Возможное расширение — набор валидных ключей (graceful rotation) или per-client ключи; не блокирует MVP | resolved-default (расширение позже) |
| <a id="q-rate-1"></a>Q-RATE-1 | Когда переходить на Redis для rate limit? | **Дефолт (MVP)**: текущий деплой — single-instance api за Traefik, `RATE_LIMIT_BACKEND=memory` (in-memory корректен в пределах одной реплики). Redis (`RATE_LIMIT_BACKEND=redis` + `REDIS_URL`) **обязателен при масштабировании api на >1 реплику** — иначе лимиты не разделяются между процессами. Триггер закрытия — решение о горизонтальном масштабировании. Детали — [07-deployment.md](07-deployment.md) | resolved-default (Redis при scale-out) |

## Открытые (блокируют конкретные части)

_Открытых блокирующих вопросов нет._ Q-CATALOG-1 и Q-LLM-1 закрыты (см. таблицу выше): prod-модель `gpt-4o`; каталог зафиксирован финальным датасетом (5 уровней + 100 эмоций EN/RU, ADR-010), activities расширяемы клиентом.

Прочие вопросы закрыты дефолтами/решениями из утверждённого плана и зафиксированы в соответствующих ADR/модульных доках. **Q-GAME-2** закрыт: механизм установки `timezone` (поле в `POST /entries`, дефолт UTC). **Q-ENTRY-1/2/3** переоценены под 2-POST дизайн (ADR-003) — resolved-by-design.
