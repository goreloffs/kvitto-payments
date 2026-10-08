from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tariff

DEFAULT_TARIFFS = [
    {"code": "basic", "title": "Basic", "price": 990_000},      # 9 900 ₽
    {"code": "standard", "title": "Standard", "price": 1_990_000},  # 19 900 ₽
    {"code": "premium", "title": "Premium", "price": 2_990_000},    # 29 900 ₽
]


def seed_tariffs(db: Session) -> None:
    """Создаёт тарифы, если их ещё нет. Идемпотентно."""
    existing_codes = set(db.scalars(select(Tariff.code)).all())
    for t in DEFAULT_TARIFFS:
        if t["code"] not in existing_codes:
            db.add(Tariff(**t))
    db.commit()
