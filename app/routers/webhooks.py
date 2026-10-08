from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Payment, PaymentStatus
from app.schemas import WebhookIn
from app.security import verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

ALLOWED_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.PENDING: {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED},
    PaymentStatus.SUCCEEDED: {PaymentStatus.REFUNDED},
    PaymentStatus.FAILED: set(),
    PaymentStatus.REFUNDED: set(),
}


@router.post("/bank")
async def bank_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()

    if not verify_webhook_signature(raw_body, x_signature):
        return JSONResponse(status_code=401, content={"error": "invalid_signature"})

    try:
        payload = WebhookIn.model_validate_json(raw_body)
    except ValidationError:
        return JSONResponse(status_code=422, content={"error": "invalid_payload"})

    payment = db.get(Payment, payload.payment_id)
    if payment is None:
        return JSONResponse(status_code=404, content={"error": "payment_not_found"})

    current = PaymentStatus(payment.status)
    if payload.status not in ALLOWED_TRANSITIONS[current]:
        return JSONResponse(status_code=409, content={"error": "invalid_transition"})

    payment.status = payload.status.value
    db.commit()
    return {"result": "ok"}
