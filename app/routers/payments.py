from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Payment, PaymentMethod, PaymentStatus, Tariff
from app.schemas import PaymentCreate, PaymentOut
from app.services import (
    InvalidPromoCode,
    apply_promo_code,
    build_schedule,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", response_model=PaymentOut)
def create_payment(
    payload: PaymentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> Payment:
    # 1. Идемпотентность: если ключ есть и платёж уже создан — вернуть его.
    if idempotency_key is not None:
        existing = db.scalar(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing

    # 2. Тариф.
    tariff = db.get(Tariff, payload.tariff_id)
    if tariff is None:
        raise HTTPException(status_code=404, detail="tariff_not_found")

    # 3. Промокод (может кинуть InvalidPromoCode → 422).
    try:
        amount, discount = apply_promo_code(tariff.price, payload.promo_code)
    except InvalidPromoCode:
        raise HTTPException(status_code=422, detail="invalid_promo_code")

    # 4. Рассрочка.
    schedule: list[int] | None = None
    if payload.method == PaymentMethod.INSTALLMENT:
        schedule = build_schedule(amount, payload.installment_months)

    # 5. Создаём платёж.
    payment = Payment(
        status=PaymentStatus.PENDING.value,
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=payload.method.value,
        installment_months=payload.installment_months,
        schedule=schedule,
        email=str(payload.email),
        idempotency_key=idempotency_key,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    response.status_code = status.HTTP_201_CREATED
    return payment


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, db: Session = Depends(get_db)) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment_not_found")
    return payment
