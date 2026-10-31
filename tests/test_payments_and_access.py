from tests.helpers import API, invoices_for


def _confirmed_invoice(client, admin, customer, activate):
    activate(customer, start="2026-01-01", expiry="2026-12-31")
    client.post(f"{API}/billing/runs", params={"run_date": "2026-01-15"}, headers=admin)
    invoice = invoices_for(client, admin, customer["id"])[0]
    assert client.post(f"{API}/invoices/{invoice['id']}/confirm", headers=admin).status_code == 200
    return invoice["id"]


def test_payments_partial_then_paid_and_overpayment_rejected(client, admin, customer, activate):
    invoice_id = _confirmed_invoice(client, admin, customer, activate)
    pay = lambda amt: client.post(f"{API}/invoices/{invoice_id}/payments", headers=admin, json={
        "method": "bank_transfer", "amount": amt, "paid_on": "2026-01-20", "note": "ref 42"})

    assert pay(50).status_code == 201
    inv = client.get(f"{API}/invoices/{invoice_id}", headers=admin).json()
    assert inv["status"] == "confirmed" and float(inv["amount_paid"]) == 50.0

    assert pay(100).status_code == 422                 # balance is 60
    assert pay(60).status_code == 201
    inv = client.get(f"{API}/invoices/{invoice_id}", headers=admin).json()
    assert inv["status"] == "paid" and float(inv["balance"]) == 0.0


def test_payment_on_draft_invoice_is_rejected(client, admin, customer, activate):
    activate(customer, start="2026-01-01", expiry="2026-12-31")
    client.post(f"{API}/billing/runs", params={"run_date": "2026-01-15"}, headers=admin)
    draft = invoices_for(client, admin, customer["id"])[0]
    r = client.post(f"{API}/invoices/{draft['id']}/payments", headers=admin, json={
        "method": "cash", "amount": 10, "paid_on": "2026-01-20"})
    assert r.status_code == 422


def test_confirmed_invoice_gets_sequential_number(client, admin, customer, activate):
    invoice_id = _confirmed_invoice(client, admin, customer, activate)
    inv = client.get(f"{API}/invoices/{invoice_id}", headers=admin).json()
    assert inv["number"].startswith("INV-2026-")


def test_overdue_filter_and_summary(client, admin, customer, activate):
    activate(customer, start="2025-06-01", expiry="2026-12-31")
    client.post(f"{API}/billing/runs", params={"run_date": "2025-06-15"}, headers=admin)
    invoice = invoices_for(client, admin, customer["id"])[0]
    client.post(f"{API}/invoices/{invoice['id']}/confirm", headers=admin)
    overdue = client.get(f"{API}/invoices", params={"overdue": True, "customer_id": customer["id"]},
                         headers=admin).json()
    assert overdue["total"] == 1
    summary = client.get(f"{API}/reports/summary", headers=admin).json()
    assert {"active_subscriptions", "outstanding_balance", "overdue", "aging"} <= summary.keys()


def test_customer_portal_is_scoped_to_owner(client, admin, customer, activate, catalog):
    sub = activate(customer)
    other = client.post(f"{API}/auth/signup", json={
        "email": f"other-{customer['id']}@example.com", "full_name": "Other Person",
        "password": "Strong#Pass1"}).json()
    from tests.helpers import login_headers
    other_headers = login_headers(client, f"other-{customer['id']}@example.com", "Strong#Pass1")

    mine = client.get(f"{API}/portal/subscriptions", headers=customer["headers"]).json()
    assert mine["total"] == 1 and mine["items"][0]["id"] == sub["id"]
    assert client.get(f"{API}/portal/subscriptions/{sub['id']}", headers=other_headers).status_code == 404
    assert client.get(f"{API}/subscriptions", headers=customer["headers"]).status_code == 403
