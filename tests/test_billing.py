from tests.helpers import API, invoices_for


def test_draft_subscriptions_are_not_billed(client, admin, customer, activate, catalog):
    client.post(f"{API}/subscriptions", headers=admin, json={
        "customer_id": customer["id"], "plan_id": catalog["plan"]["id"], "quantity": 1,
        "start_date": "2026-01-01", "expiry_date": "2026-12-31"})
    r = client.post(f"{API}/billing/runs", params={"run_date": "2026-03-15"}, headers=admin)
    assert r.status_code == 201
    assert invoices_for(client, admin, customer["id"]) == []


def test_billing_catches_up_and_never_double_bills(client, admin, customer, activate):
    activate(customer)
    first = client.post(f"{API}/billing/runs", params={"run_date": "2026-03-15"}, headers=admin).json()
    assert first["invoices_created"] == 3                          # Jan, Feb, Mar

    invoices = invoices_for(client, admin, customer["id"])
    assert [i["period_start"] for i in invoices] == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert all(float(i["total"]) == 110.0 for i in invoices)       # 100 + 10% tax
    assert all(float(i["tax_total"]) == 10.0 for i in invoices)

    second = client.post(f"{API}/billing/runs", params={"run_date": "2026-03-15"}, headers=admin).json()
    assert second["invoices_created"] == 0
    assert len(invoices_for(client, admin, customer["id"])) == 3


def test_discount_usage_limit_is_enforced(client, admin, customer, activate):
    discount = client.post(f"{API}/catalog/discounts", headers=admin, json={
        "name": "Seat promo", "kind": "percent", "value": 10, "scope": "subscription",
        "start_date": "2026-01-01", "usage_limit": 2}).json()
    activate(customer, discount_id=discount["id"])
    client.post(f"{API}/billing/runs", params={"run_date": "2026-03-15"}, headers=admin)

    invoices = invoices_for(client, admin, customer["id"])
    # 10% off 100 = 10 discount, tax 9 on the remaining 90, total 99. Only two uses are allowed.
    assert [float(i["total"]) for i in invoices] == [99.0, 99.0, 110.0]
    assert float(invoices[0]["discount_total"]) == 10.0
    assert float(invoices[2]["discount_total"]) == 0.0

    stored = next(d for d in client.get(f"{API}/catalog/discounts", headers=admin).json()
                  if d["id"] == discount["id"])
    assert stored["used_count"] == 2


def test_cancelled_invoice_returns_discount_use(client, admin, customer, activate):
    discount = client.post(f"{API}/catalog/discounts", headers=admin, json={
        "name": "Return test", "kind": "fixed", "value": 5, "scope": "subscription",
        "start_date": "2026-01-01", "usage_limit": 5}).json()
    activate(customer, discount_id=discount["id"])
    client.post(f"{API}/billing/runs", params={"run_date": "2026-01-15"}, headers=admin)
    invoice = invoices_for(client, admin, customer["id"])[0]
    assert client.post(f"{API}/invoices/{invoice['id']}/cancel", headers=admin).status_code == 200
    stored = next(d for d in client.get(f"{API}/catalog/discounts", headers=admin).json()
                  if d["id"] == discount["id"])
    assert stored["used_count"] == 0


def test_subscription_lifecycle_rejects_invalid_moves(client, admin, customer, catalog):
    sub = client.post(f"{API}/subscriptions", headers=admin, json={
        "customer_id": customer["id"], "plan_id": catalog["plan"]["id"], "quantity": 1,
        "start_date": "2026-01-01", "expiry_date": "2026-12-31"}).json()
    jump = client.post(f"{API}/subscriptions/{sub['id']}/transition", headers=admin, json={"status": "active"})
    assert jump.status_code == 422
    history = client.get(f"{API}/subscriptions/{sub['id']}", headers=admin).json()["history"]
    assert [h["to"] for h in history] == ["draft"]


def test_quotation_from_template_carries_validity(client, admin, customer, catalog):
    template = client.post(f"{API}/catalog/quotation-templates", headers=admin, json={
        "name": "Enterprise 30-day", "plan_id": catalog["plan"]["id"], "validity_days": 30}).json()
    r = client.post(f"{API}/subscriptions/from-template/{template['id']}", headers=admin, json={
        "customer_id": customer["id"], "quantity": 5, "start_date": "2026-01-01", "expiry_date": "2026-12-31"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "quotation"
    assert body["quotation_valid_until"] is not None
    confirm = client.post(f"{API}/subscriptions/{body['id']}/transition", headers=admin,
                          json={"status": "confirmed"})
    assert confirm.status_code == 200


def test_auto_close_plan_closes_at_expiry(client, admin, customer, activate):
    activate(customer, start="2026-01-01", expiry="2026-02-01")
    client.post(f"{API}/billing/runs", params={"run_date": "2026-06-01"}, headers=admin)
    subs = client.get(f"{API}/subscriptions", params={"customer_id": customer["id"]}, headers=admin).json()
    assert subs["items"][0]["status"] == "closed"
    assert len(invoices_for(client, admin, customer["id"])) == 1   # only the January period
