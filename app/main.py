from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import payments, tariffs, webhooks
from app.seed import seed_tariffs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Для SQLite (локальная разработка, тесты) — создаём таблицы автоматически.
    # Для Postgres (Docker) — схема управляется через Alembic, см. README.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_tariffs(db)

    yield


app = FastAPI(title="Kvitto Payments", lifespan=lifespan)

app.include_router(tariffs.router)
app.include_router(payments.router)
app.include_router(webhooks.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
