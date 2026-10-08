import hashlib
import hmac

from app.config import settings


def verify_webhook_signature(body: bytes, signature_hex: str | None) -> bool:
    """
    Проверяет HMAC-SHA256 подпись вебхука.

    Если WEBHOOK_SECRET не задан, проверка считается отключённой и всегда True.
    Если задан — сравнивает hex-подпись, используя hmac.compare_digest (constant-time).
    """
    if settings.webhook_secret is None or settings.webhook_secret == "":
        return True
    if signature_hex is None:
        return False

    expected = hmac.new(
        key=settings.webhook_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_hex)
