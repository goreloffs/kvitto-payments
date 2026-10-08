from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
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


@router.get("", response_model=list[PaymentOut])
def list_payments(
    email: str | None = Query(default=None),
    payment_status: PaymentStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[Payment]:
    stmt = select(Payment).order_by(Payment.id)
    if email is not None:
        stmt = stmt.where(Payment.email == email)
    if payment_status is not None:
        stmt = stmt.where(Payment.status == payment_status.value)
    return list(db.scalars(stmt).all())


@router.post("", response_model=PaymentOut)
def create_payment(
    payload: PaymentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> Payment:
    if idempotency_key is not None:
        existing = db.scalar(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing

    tariff = db.get(Tariff, payload.tariff_id)
    if tariff is None:
        raise HTTPException(status_code=404, detail="tariff_not_found")

    try:
        amount, discount = apply_promo_code(tariff.price, payload.promo_code)
    except InvalidPromoCode:
        raise HTTPException(status_code=422, detail="invalid_promo_code") from None

    schedule: list[int] | None = None
    if payload.method == PaymentMethod.INSTALLMENT:
        schedule = build_schedule(amount, payload.installment_months)

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