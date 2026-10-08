from app.models import PaymentMethod

PROMO_CODE = "KVITT010"
PROMO_DISCOUNT_PERCENT = 10


class InvalidPromoCode(ValueError):
    """Промокод не распознан. Роутер вернёт 422."""


class InvalidInstallment(ValueError):
    """Рассрочка запрошена с некорректными параметрами."""


def apply_promo_code(price: int, promo_code: str | None) -> tuple[int, int]:
    """
    Возвращает (amount_to_pay, discount).
    Всё в копейках, целые числа.
    Если промокода нет — discount=0.
    Если промокод неизвестен — InvalidPromoCode.
    """
    if promo_code is None:
        return price, 0

    normalized = promo_code.strip().upper()
    if normalized != PROMO_CODE:
        raise InvalidPromoCode(promo_code)

    discount = price * PROMO_DISCOUNT_PERCENT // 100
    return price - discount, discount


def build_schedule(amount: int, months: int) -> list[int]:
    """
    Делит сумму на months равных (насколько возможно) частей.
    Сумма всех элементов ровно равна amount.
    Лишние копейки (остаток от деления) — в первые платежи.
    """
    if amount <= 0:
        raise InvalidInstallment("amount must be positive")
    if months not in (3, 6, 12):
        raise InvalidInstallment("months must be 3, 6 or 12")

    base = amount // months
    remainder = amount % months
    return [base + 1] * remainder + [base] * (months - remainder)


def is_installment(method: PaymentMethod) -> bool:
    return method == PaymentMethod.INSTALLMENT
