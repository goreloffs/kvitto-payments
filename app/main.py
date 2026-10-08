from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, SessionLocal, engine
from app.seed import seed_tariffs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_tariffs(db)
    yield
    # shutdown — пока нечего чистить


app = FastAPI(title="Kvitto Payments", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
