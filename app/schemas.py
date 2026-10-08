from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import PaymentMethod, PaymentStatus


# ---------- Tariffs ----------

class TariffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: int


# ---------- Payments: вход ----------

class PaymentCreate(BaseModel):
    tariff_id: int = Field(gt=0)
    email: EmailStr
    method: Literal[PaymentMethod.CARD, PaymentMethod.SBP, PaymentMethod.INSTALLMENT]
    installment_months: Literal[3, 6, 12] | None = None
    promo_code: str | None = None

    @model_validator(mode="after")
    def check_installment(self) -> "PaymentCreate":
        if self.method == PaymentMethod.INSTALLMENT:
            if self.installment_months is None:
                raise ValueError("installment_months is required for installment")
        else:
            if self.installment_months is not None:
                raise ValueError("installment_months is only allowed for installment")
        return self


# ---------- Payments: выход ----------

class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: PaymentStatus
    tariff_id: int
    amount: int
    discount: int
    method: PaymentMethod
    installment_months: int | None
    schedule: list[int] | None
    email: EmailStr
    created_at: datetime


# ---------- Webhook ----------

class WebhookIn(BaseModel):
    payment_id: int
    status: PaymentStatus
