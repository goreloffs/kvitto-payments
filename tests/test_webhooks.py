

def _create_payment(client) -> int:
    resp = client.post(
        "/payments",
        json={
            "tariff_id": 1,
            "email": "student@example.com",
            "method": "card",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_webhook_missing_payment_returns_404(client):
    resp = client.post(
        "/webhooks/bank", json={"payment_id": 999999, "status": "succeeded"}
    )
    assert resp.status_code == 404


def test_webhook_pending_to_succeeded(client):
    pid = _create_payment(client)
    resp = client.post(
        "/webhooks/bank", json={"payment_id": pid, "status": "succeeded"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"result": "ok"}
    assert client.get(f"/payments/{pid}").json()["status"] == "succeeded"


def test_webhook_pending_to_failed(client):
    pid = _create_payment(client)
    resp = client.post(
        "/webhooks/bank", json={"payment_id": pid, "status": "failed"}
    )
    assert resp.status_code == 200
    assert client.get(f"/payments/{pid}").json()["status"] == "failed"


def test_webhook_succeeded_to_refunded(client):
    pid = _create_payment(client)
    client.post("/webhooks/bank", json={"payment_id": pid, "status": "succeeded"})
    resp = client.post(
        "/webhooks/bank", json={"payment_id": pid, "status": "refunded"}
    )
    assert resp.status_code == 200
    assert client.get(f"/payments/{pid}").json()["status"] == "refunded"


def test_webhook_invalid_transition_returns_409_and_keeps_status(client):
    pid = _create_payment(client)
    # pending -> refunded запрещён
    resp = client.post(
        "/webhooks/bank", json={"payment_id": pid, "status": "refunded"}
    )
    assert resp.status_code == 409
    assert resp.json() == {"error": "invalid_transition"}
    # статус не изменился
    assert client.get(f"/payments/{pid}").json()["status"] == "pending"


def test_webhook_refunded_is_terminal(client):
    pid = _create_payment(client)
    client.post("/webhooks/bank", json={"payment_id": pid, "status": "succeeded"})
    client.post("/webhooks/bank", json={"payment_id": pid, "status": "refunded"})
    # любой дальнейший переход — 409
    for bad in ("succeeded", "failed", "refunded", "pending"):
        resp = client.post(
            "/webhooks/bank", json={"payment_id": pid, "status": bad}
        )
        assert resp.status_code == 409, f"expected 409 for {bad}"


# ---------- HMAC ----------

import hashlib
import hmac
import json

from app.config import settings


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_without_secret_is_open(client):
    # по умолчанию webhook_secret = None → подпись не проверяется
    pid = _create_payment(client)
    resp = client.post(
        "/webhooks/bank", json={"payment_id": pid, "status": "succeeded"}
    )
    assert resp.status_code == 200


def test_webhook_with_secret_valid_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "topsecret")
    pid = _create_payment(client)
    body = json.dumps({"payment_id": pid, "status": "succeeded"}).encode()
    sig = _sign(body, "topsecret")
    resp = client.post(
        "/webhooks/bank",
        content=body,
        headers={"X-Signature": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200


def test_webhook_with_secret_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "topsecret")
    pid = _create_payment(client)
    body = json.dumps({"payment_id": pid, "status": "succeeded"}).encode()
    resp = client.post(
        "/webhooks/bank",
        content=body,
        headers={"X-Signature": "badbadbad", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401
    # статус не изменился
    assert client.get(f"/payments/{pid}").json()["status"] == "pending"


def test_webhook_with_secret_missing_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "topsecret")
    pid = _create_payment(client)
    body = json.dumps({"payment_id": pid, "status": "succeeded"}).encode()
    resp = client.post(
        "/webhooks/bank",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401
