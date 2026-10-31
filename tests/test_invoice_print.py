from app.database import SessionLocal
from app.models import Invoice, InvoiceLine, User
from tests.helpers import API, invoices_for, login_headers, unique, PASSWORD


def _billed_invoice(client, admin, customer, activate, **extra):
    """One confirmed invoice for January 2026: plan 100 + 10% tax = 110, with the given extras."""
    activate(customer, start="2026-01-01", expiry="2026-12-31", **extra)
    client.post(f"{API}/billing/runs", params={"run_date": "2026-01-15"}, headers=admin)
    inv = invoices_for(client, admin, customer["id"])[0]
    assert client.post(f"{API}/invoices/{inv['id']}/confirm", headers=admin).status_code == 200
    return inv["id"]


def test_staff_gets_full_invoice_document_data(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    r = client.get(f"{API}/invoices/{inv_id}", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["company_name"] == "Brightloop Billing"
    assert body["customer"]["full_name"] == "Test Customer"
    assert body["customer"]["email"] == customer["email"]
    assert body["subscription_number"].startswith("SUB-")
    assert body["plan_name"]
    assert body["number"].startswith("INV-")
    assert len(body["lines"]) == 1
    assert float(body["total"]) == 110.0 and float(body["tax_total"]) == 10.0
    assert float(body["balance"]) == 110.0


def test_customer_sees_own_invoice_only(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    owner = client.get(f"{API}/portal/invoices/{inv_id}", headers=customer["headers"])
    assert owner.status_code == 200
    assert owner.json()["customer"]["email"] == customer["email"]

    other = client.post(f"{API}/auth/signup", json={
        "email": f"{unique('other')}@example.com", "full_name": "Other Person", "password": PASSWORD}).json()
    other_headers = login_headers(client, other["email"], PASSWORD)
    assert client.get(f"{API}/portal/invoices/{inv_id}", headers=other_headers).status_code == 404


def test_customer_cannot_use_staff_invoice_endpoints(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    assert client.get(f"{API}/invoices/{inv_id}", headers=customer["headers"]).status_code == 403
    assert client.get(f"{API}/invoices/{inv_id}/print", headers=customer["headers"]).status_code == 403


def test_unauthenticated_request_is_rejected(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    assert client.get(f"{API}/invoices/{inv_id}").status_code == 401
    assert client.get(f"{API}/portal/invoices/{inv_id}").status_code == 401


def test_draft_invoice_hidden_from_customer_but_visible_to_staff(client, admin, customer, activate):
    activate(customer, start="2026-01-01", expiry="2026-12-31")
    client.post(f"{API}/billing/runs", params={"run_date": "2026-01-15"}, headers=admin)
    draft = invoices_for(client, admin, customer["id"])[0]
    assert client.get(f"{API}/portal/invoices/{draft['id']}", headers=customer["headers"]).status_code == 404
    assert client.get(f"{API}/invoices/{draft['id']}", headers=admin).status_code == 200


def test_multiple_line_items_are_returned_in_order(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    with SessionLocal() as db:
        db.add(InvoiceLine(invoice_id=inv_id, description="Support add-on", quantity=2, unit_price=50,
                           subtotal=100, discount_amount=0, tax_rate=10, tax_amount=10, line_total=110))
        db.commit()
    lines = client.get(f"{API}/invoices/{inv_id}", headers=admin).json()["lines"]
    assert [l["description"] for l in lines][-1] == "Support add-on"
    assert len(lines) == 2
    assert lines[1]["quantity"] == 2 and float(lines[1]["line_total"]) == 110.0


def test_discount_tax_and_partial_payments_are_reflected(client, admin, customer, activate):
    discount = client.post(f"{API}/catalog/discounts", headers=admin, json={
        "name": unique("Print promo"), "kind": "percent", "value": 10, "scope": "subscription",
        "start_date": "2026-01-01"}).json()
    inv_id = _billed_invoice(client, admin, customer, activate, discount_id=discount["id"])
    client.post(f"{API}/invoices/{inv_id}/payments", headers=admin, json={
        "method": "bank_transfer", "amount": 40, "paid_on": "2026-01-20", "note": "UTR 9"})
    body = client.get(f"{API}/invoices/{inv_id}", headers=admin).json()
    assert float(body["discount_total"]) == 10.0      # 10% of 100
    assert float(body["tax_total"]) == 9.0            # 10% of the discounted 90
    assert float(body["total"]) == 99.0
    assert float(body["amount_paid"]) == 40.0
    assert float(body["balance"]) == 59.0
    assert body["payments"][0]["note"] == "UTR 9"


# ---- /invoices/{id}/print: HTML document -----------------------------------------------------

def _print(client, headers, inv_id):
    return client.get(f"{API}/invoices/{inv_id}/print", headers=headers)


def test_print_returns_html_document_not_plain_text(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    r = _print(client, admin, inv_id)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"].startswith("inline;")
    assert r.text.lstrip().startswith("<!DOCTYPE html>")
    assert "<table" in r.text and "TOTAL 110" not in r.text


def test_print_contains_all_invoice_details(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    data = client.get(f"{API}/invoices/{inv_id}", headers=admin).json()
    html = _print(client, admin, inv_id).text
    assert "Brightloop Billing" in html                       # configured company name
    assert data["number"] in html                             # INV-...
    assert "Test Customer" in html and customer["email"] in html
    assert "01 Jan 2026" in html                              # issue date / period start
    assert "31 Jan 2026" in html                              # period end
    assert data["subscription_number"] in html and data["plan_name"] in html
    assert "Issue date" in html and "Due date" in html and "Billing period" in html
    assert "Qty" in html and "Unit price" in html and "Discount" in html and "Tax rate" in html
    for label in ("Subtotal", "Total", "Amount paid", "Balance due"):
        assert label in html
    assert "110.00" in html and "10.00" in html and "100.00" in html
    assert "15 Jan 2026" in html                              # due date (14-day terms from 01 Jan)
    assert "-0.00" not in html                                # no discount -> no minus sign


def test_print_shows_discount_tax_payments_and_balance(client, admin, customer, activate):
    discount = client.post(f"{API}/catalog/discounts", headers=admin, json={
        "name": unique("Print promo"), "kind": "percent", "value": 10, "scope": "subscription",
        "start_date": "2026-01-01"}).json()
    inv_id = _billed_invoice(client, admin, customer, activate, discount_id=discount["id"])
    client.post(f"{API}/invoices/{inv_id}/payments", headers=admin, json={
        "method": "bank_transfer", "amount": 40, "paid_on": "2026-01-20", "note": "UTR 9"})
    html = _print(client, admin, inv_id).text
    assert "-10.00" in html          # discount total
    assert "9.00" in html            # tax on discounted 90
    assert "99.00" in html           # total
    assert "40.00" in html           # amount paid
    assert "59.00" in html           # outstanding balance
    assert "Payments received" in html and "UTR 9" in html and "Bank Transfer" in html


def test_print_lists_every_line_item_with_quantity_and_price(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    with SessionLocal() as db:
        db.add(InvoiceLine(invoice_id=inv_id, description="Support add-on", quantity=2, unit_price=50,
                           subtotal=100, discount_amount=0, tax_rate=10, tax_amount=10, line_total=110))
        db.commit()
    html = _print(client, admin, inv_id).text
    assert "Support add-on" in html
    assert html.count("<tr>") >= 4        # header row + 2 lines + totals rows
    assert "50.00" in html and "<td class='num'>2</td>" in html


def test_print_escapes_customer_and_line_values(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    evil = "<script>alert(1)</script>"
    with SessionLocal() as db:
        inv = db.get(Invoice, inv_id)
        db.get(User, inv.customer_id).full_name = '<img src=x onerror=alert(1)> & "Co"'
        db.add(InvoiceLine(invoice_id=inv_id, description=evil, quantity=1, unit_price=1,
                           subtotal=1, discount_amount=0, tax_rate=0, tax_amount=0, line_total=1))
        db.commit()
    html = _print(client, admin, inv_id).text
    assert evil not in html and "<img src=x" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt; &amp; &quot;Co&quot;" in html
    assert html.count("<script") == 0
    assert "default-src 'none'" in _print(client, admin, inv_id).headers["content-security-policy"]


def test_print_works_for_draft_invoice_with_placeholder_number(client, admin, customer, activate):
    activate(customer, start="2026-01-01", expiry="2026-12-31")
    client.post(f"{API}/billing/runs", params={"run_date": "2026-01-15"}, headers=admin)
    draft = invoices_for(client, admin, customer["id"])[0]
    r = _print(client, admin, draft["id"])
    assert r.status_code == 200
    assert 'class="status draft"' in r.text
    assert (draft["number"] or f"DRAFT-{draft['id']}") in r.text


def test_staff_role_can_print(client, admin, customer, activate, make_staff):
    inv_id = _billed_invoice(client, admin, customer, activate)
    r = _print(client, make_staff("staff"), inv_id)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")


def test_print_missing_invoice_returns_404(client, admin):
    r = _print(client, admin, 99999999)
    assert r.status_code == 404
    assert r.json()["detail"] == "Invoice not found"


def test_print_requires_authentication(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    assert client.get(f"{API}/invoices/{inv_id}/print").status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert _print(client, bad, inv_id).status_code == 401


def test_print_forbidden_for_customers_including_the_owner(client, admin, customer, activate):
    inv_id = _billed_invoice(client, admin, customer, activate)
    owner = _print(client, customer["headers"], inv_id)
    assert owner.status_code == 403
    assert "Brightloop" not in owner.text and customer["email"] not in owner.text
    other = client.post(f"{API}/auth/signup", json={
        "email": f"{unique('other')}@example.com", "full_name": "Other Person", "password": PASSWORD}).json()
    other_headers = login_headers(client, other["email"], PASSWORD)
    assert _print(client, other_headers, inv_id).status_code == 403
