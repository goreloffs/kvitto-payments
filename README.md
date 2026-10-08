# Kvitto Payments API

Небольшой сервис на FastAPI для приёма оплаты курсов онлайн-школой через Квитто.
Реализует создание платежей, применение промокода, график рассрочки, идемпотентность
и обработку вебхуков от банка.

## Стек

- Python 3.11+ (проверено на 3.14)
- FastAPI 0.143, Pydantic v2, pydantic-settings
- SQLAlchemy 2.1 + SQLite (по умолчанию)
- pytest + httpx (через `fastapi.testclient`)
- uvicorn

## Установка и запуск

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

## Тесты

```bash
pytest -v
```

22 теста покрывают: тарифы, создание платежа с промокодом (в т.ч. в нижнем регистре),
график рассрочки для 3/6/12 месяцев, идемпотентность, разрешённые/запрещённые переходы
статусов, 404 на несуществующий платёж.

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
возвращается он же со статусом 200 (второй не создаётся). Иначе — 201.

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
  "created_at": "2026-10-08T17:33:44.264819"
}
```

### `GET /payments/{id}`

Возвращает платёж или 404.

```bash
curl http://127.0.0.1:8000/payments/1
```

### `POST /webhooks/bank`

Банк сообщает о смене статуса. Тело: `payment_id`, `status`.

Допустимые переходы:
- `pending → succeeded`
- `pending → failed`
- `succeeded → refunded`

Платежа нет — 404.
Запрещённый переход — 409 `{"error": "invalid_transition"}`, статус не меняется.
Успех — 200 `{"result": "ok"}`.

```bash
curl -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"payment_id": 1, "status": "succeeded"}'
```

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
```

## Конфигурация

Настройки читаются из переменных окружения или `.env` (шаблон — `.env.example`):

- `DATABASE_URL` — строка подключения SQLAlchemy. По умолчанию `sqlite:///./kvitto.db`.
- `WEBHOOK_SECRET` — секрет для проверки подписи вебхуков (пока не используется).

## Заметки

- Тесты используют отдельную in-memory SQLite с `StaticPool`, боевая база не затрагивается.
- `Idempotency-Key` хранится в БД как уникальный ключ (`unique`, `nullable`).
- Формат ошибок валидации — стандартный ответ FastAPI с кодом 422.
