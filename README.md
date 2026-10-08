# Kvitto Payments API

Небольшой сервис на FastAPI для приёма оплаты курсов онлайн-школой через Квитто.
Реализует создание платежей, применение промокода, график рассрочки, идемпотентность,
обработку вебхуков от банка с HMAC-подписью и запуск через Docker + PostgreSQL.

## Стек

- Python 3.11+ (проверено на 3.14)
- FastAPI 0.143, Pydantic v2, pydantic-settings
- SQLAlchemy 2.1 + SQLite (по умолчанию) / PostgreSQL (в Docker)
- pytest + httpx (через `fastapi.testclient`)
- ruff — линтер
- uvicorn
- Docker + Docker Compose (опционально)

## Установка и запуск (локально, SQLite)

```bash
# 1. Клонировать
git clone https://github.com/goreloffs/kvitto-payments.git
cd kvitto-payments

# 2. Виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Зависимости
pip install -r requirements.txt

# 4. Конфиг (опционально)
cp .env.example .env

# 5. Запуск
uvicorn app.main:app --reload
```

Сервис поднимется на `http://127.0.0.1:8000`.
Swagger — `http://127.0.0.1:8000/docs`.

При старте автоматически:
- создаются таблицы (`Base.metadata.create_all`);
- засеиваются тарифы: `basic` = 990 000 копеек, `standard` = 1 990 000, `premium` = 2 990 000.

## Запуск через Docker

Требуется Docker и Docker Compose v2+.

```bash
docker compose up --build -d
```

Поднимаются два контейнера:
- `db` — PostgreSQL 16 (alpine), данные в named volume `pgdata`;
- `api` — FastAPI-приложение на `python:3.12-slim`, слушает `0.0.0.0:8000`.

API стартует **после** того, как Postgres пройдёт healthcheck (`condition: service_healthy`),
поэтому гонки при инициализации нет. Но uvicorn внутри контейнера поднимается 1–3 секунды —
после `docker compose up` дождись `Application startup complete` в логах:

```bash
docker compose logs -f api
```

Проверка:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/tariffs
docker compose exec db psql -U kvitto -d kvitto -c "SELECT code, price FROM tariffs;"
```

Остановить (данные Postgres сохранятся в volume):

```bash
docker compose down
```

Остановить и удалить данные:

```bash
docker compose down -v
```

С Docker используется PostgreSQL, без Docker — SQLite (см. `.env.example`).

## Тесты

```bash
pytest -v
```

29 тестов покрывают:
- тарифы;
- создание платежа с промокодом и без, в т.ч. промокод в нижнем регистре;
- график рассрочки для 3/6/12 месяцев;
- идемпотентность по `Idempotency-Key`;
- разрешённые и запрещённые переходы статусов;
- 404 на несуществующий платёж;
- HMAC-подпись вебхука (валидная, невалидная, отсутствующая).

Тесты используют отдельную in-memory SQLite с `StaticPool` — боевая база не затрагивается.

## Эндпоинты

### `GET /tariffs`

Список тарифов.

```bash
curl http://127.0.0.1:8000/tariffs
```

```json
[
  {"id": 1, "title": "Basic", "price": 990000},
  {"id": 2, "title": "Standard", "price": 1990000},
  {"id": 3, "title": "Premium", "price": 2990000}
]
```

### `POST /payments`

Создаёт платёж. Тело: `tariff_id`, `email`, `method` (`card` | `sbp` | `installment`),
`installment_months` (обязательно для `installment`, значения 3/6/12), опционально `promo_code`.

Если передан заголовок `Idempotency-Key` и платёж с таким ключом уже существует —
возвращается он же со статусом **200** (второй не создаётся). Иначе — **201**.

Без промокода:

```bash
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id": 2, "email": "student@example.com", "method": "card"}'
```

С промокодом (регистр не важен):

```bash
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id": 2, "email": "student@example.com", "method": "card", "promo_code": "kvitt010"}'
```

Рассрочка на 3 месяца:

```bash
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id": 2, "email": "student@example.com", "method": "installment", "installment_months": 3}'
```

С идемпотентностью:

```bash
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-unique-key-123" \
  -d '{"tariff_id": 1, "email": "student@example.com", "method": "card"}'
```

Пример ответа:

```json
{
  "id": 1,
  "status": "pending",
  "tariff_id": 2,
  "amount": 1990000,
  "discount": 0,
  "method": "installment",
  "installment_months": 3,
  "schedule": [663334, 663333, 663333],
  "email": "student@example.com",
  "created_at": "2026-10-08T18:54:46.400919Z"
}
```

### `GET /payments/{id}`

Возвращает платёж или 404.

```bash
curl http://127.0.0.1:8000/payments/1
```

### `GET /payments`

Список платежей с опциональными фильтрами `email` и `status`.

```bash
curl "http://127.0.0.1:8000/payments"
curl "http://127.0.0.1:8000/payments?email=student@example.com"
curl "http://127.0.0.1:8000/payments?status=succeeded"
```

### `POST /webhooks/bank`

Банк сообщает о смене статуса. Тело: `payment_id`, `status`.

Допустимые переходы:
- `pending → succeeded`
- `pending → failed`
- `succeeded → refunded`

Платежа нет — **404**.
Запрещённый переход — **409** `{"error": "invalid_transition"}`, статус не меняется.
Успех — **200** `{"result": "ok"}`.

```bash
curl -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"payment_id": 1, "status": "succeeded"}'
```

#### Проверка подписи вебхука

Если переменная окружения `WEBHOOK_SECRET` задана, эндпоинт `POST /webhooks/bank`
проверяет заголовок `X-Signature` — HMAC-SHA256 от **сырого тела** запроса, hex-строка.

- секрет не задан → проверка отключена (удобно для локальной разработки);
- секрет задан, подпись валидна → обработка продолжается;
- секрет задан, подпись неверна или отсутствует → **401**, статус платежа не меняется.

Пример подписи на Python:

```python
import hashlib, hmac, json

body = json.dumps({"payment_id": 1, "status": "succeeded"}).encode()
sig = hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()

import httpx
httpx.post(
    "http://127.0.0.1:8000/webhooks/bank",
    content=body,
    headers={"X-Signature": sig, "Content-Type": "application/json"},
)
```

Сравнение подписей делается через `hmac.compare_digest` (constant-time), чтобы избежать
тайминг-атак.

## Бизнес-правила

**Деньги.** Все суммы — целые числа в копейках. Никаких float.

**Промокод.** `KVITT010` даёт −10 % от цены тарифа. Регистр не важен.
Неизвестный код — 422.

**График рассрочки.** Сумма к оплате делится на срок в копейках.
Сумма всех платежей графика ровно равна сумме к оплате, лишние копейки уходят
в первые платежи. Пример: 1 990 000 на 3 месяца → `[663334, 663333, 663333]`.

**Статусы.** Новый платёж — `pending`. Разрешены только переходы:
`pending → succeeded`, `pending → failed`, `succeeded → refunded`.
Остальные запрещены.

**Идемпотентность.** При наличии заголовка `Idempotency-Key` повторный запрос
с тем же ключом не создаёт новый платёж, а возвращает существующий со статусом 200.

## Структура проекта

```
app/
  config.py       # настройки через pydantic-settings
  database.py     # engine, SessionLocal, Base, get_db
  models.py       # SQLAlchemy-модели: Tariff, Payment
  schemas.py      # Pydantic-схемы: TariffOut, PaymentCreate, PaymentOut, WebhookIn
  services.py     # бизнес-логика: промокод, график рассрочки
  security.py     # HMAC-SHA256 проверка подписи вебхука
  seed.py         # создание тарифов при старте
  main.py         # сборка приложения, lifespan, подключение роутеров
  routers/
    tariffs.py
    payments.py
    webhooks.py
tests/
  conftest.py     # фикстуры: тестовый engine, client, override get_db
  test_tariffs.py
  test_payments.py
  test_webhooks.py
Dockerfile
docker-compose.yml
pyproject.toml    # конфиг ruff
```

## Конфигурация

Настройки читаются из переменных окружения или `.env` (шаблон — `.env.example`):

- `DATABASE_URL` — строка подключения SQLAlchemy. По умолчанию `sqlite:///./kvitto.db`.
  В Docker переопределяется на `postgresql+psycopg://kvitto:kvitto@db:5432/kvitto`.
- `WEBHOOK_SECRET` — секрет для проверки HMAC-SHA256 подписи вебхуков.
  Если пусто — проверка отключена.

## Линтер и CI

```bash
ruff check .
ruff check . --fix    # автофикс
```

GitHub Actions прогоняет `ruff check .` и `pytest -v` на каждый push в `main`.

## Миграции (Alembic)

Схема БД управляется через Alembic. Локально (SQLite) таблицы создаются автоматически
через `Base.metadata.create_all` в `lifespan`. В Docker (PostgreSQL) схема создаётся
через `alembic upgrade head` при старте контейнера `api`.

### Команды

```bash
# Применить все миграции
alembic upgrade head

# Откатить последнюю
alembic downgrade -1

# Сгенерировать новую миграцию по изменениям в моделях
alembic revision --autogenerate -m "описание изменения"

# История миграций
alembic history

# Текущая ревизия
alembic current

## Заметки

- Тесты используют отдельную in-memory SQLite с `StaticPool`, боевая база не затрагивается.
- `Idempotency-Key` хранится в БД как уникальный ключ (`unique`, `nullable`).
- Формат ошибок валидации — стандартный ответ FastAPI с кодом 422.
- На SQLite `created_at` сериализуется без суффикса таймзоны, на PostgreSQL — с `Z`.
  Формат в задании не оговорён, оба варианта допустимы.
