from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Payment, PaymentStatus
from app.schemas import WebhookIn

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

ALLOWED_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.PENDING: {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED},
    PaymentStatus.SUCCEEDED: {PaymentStatus.REFUNDED},
    PaymentStatus.FAILED: set(),
    PaymentStatus.REFUNDED: set(),
}


@router.post("/bank")
def bank_webhook(payload: WebhookIn, db: Session = Depends(get_db)):
    payment = db.get(Payment, payload.payment_id)
    if payment is None:
        return JSONResponse(status_code=404, content={"error": "payment_not_found"})

    current = PaymentStatus(payment.status)
    new = payload.status

    if new not in ALLOWED_TRANSITIONS[current]:
        return JSONResponse(
            status_code=409, content={"error": "invalid_transition"}
        )

    payment.status = new.value
    db.commit()
    return {"result": "ok"}
