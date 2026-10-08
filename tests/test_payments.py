import pytest


def _payload(tariff_id=2, **extra):
    return {
        "tariff_id": tariff_id,
        "email": "student@example.com",
        "method": "card",
        **extra,
    }


def test_create_payment_without_promo(client):
    resp = client.post("/payments", json=_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount"] == 1_990_000
    assert body["discount"] == 0
    assert body["status"] == "pending"
    assert body["schedule"] is None


def test_create_payment_with_promo_uppercase(client):
    resp = client.post("/payments", json=_payload(promo_code="KVITT010"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount"] == 1_791_000
    assert body["discount"] == 199_000


def test_create_payment_with_promo_lowercase(client):
    resp = client.post("/payments", json=_payload(promo_code="kvitt010"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["amount"] == 1_791_000
    assert body["discount"] == 199_000


def test_create_payment_with_unknown_promo_returns_422(client):
    resp = client.post("/payments", json=_payload(promo_code="NOPE"))
    assert resp.status_code == 422


@pytest.mark.parametrize("months", [3, 6, 12])
def test_installment_schedule_sums_to_amount(client, months):
    resp = client.post(
        "/payments",
        json=_payload(method="installment", installment_months=months),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["installment_months"] == months
    assert len(body["schedule"]) == months
    assert sum(body["schedule"]) == body["amount"] == 1_990_000


def test_installment_without_months_returns_422(client):
    resp = client.post("/payments", json=_payload(method="installment"))
    assert resp.status_code == 422


def test_installment_with_bad_months_returns_422(client):
    resp = client.post(
        "/payments",
        json=_payload(method="installment", installment_months=5),
    )
    assert resp.status_code == 422


def test_installment_months_not_allowed_for_card(client):
    resp = client.post(
        "/payments", json=_payload(method="card", installment_months=3)
    )
    assert resp.status_code == 422


def test_idempotency_returns_same_payment(client):
    headers = {"Idempotency-Key": "fixed-key-1"}
    first = client.post("/payments", json=_payload(), headers=headers)
    second = client.post("/payments", json=_payload(), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_idempotency_different_keys_create_two_payments(client):
    a = client.post("/payments", json=_payload(), headers={"Idempotency-Key": "k-a"})
    b = client.post("/payments", json=_payload(), headers={"Idempotency-Key": "k-b"})
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["id"] != b.json()["id"]


def test_get_existing_payment(client):
    created = client.post("/payments", json=_payload()).json()
    resp = client.get(f"/payments/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_missing_payment_returns_404(client):
    resp = client.get("/payments/999999")
    assert resp.status_code == 404


def test_create_payment_for_missing_tariff_returns_404(client):
    resp = client.post("/payments", json=_payload(tariff_id=999))
    assert resp.status_code == 404
