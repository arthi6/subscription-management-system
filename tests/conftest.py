import os
from pathlib import Path

# Tests run against a throwaway SQLite file. Set before the app is imported.
DB_FILE = Path("test_subscriptions.db")
if DB_FILE.exists():
    DB_FILE.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

from tests.helpers import API, PASSWORD, invoices_for, login_headers, unique  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin(client):
    return login_headers(client, settings.bootstrap_admin_email, settings.bootstrap_admin_password)


@pytest.fixture
def make_staff(client, admin):
    def _make(role="staff"):
        email = f"{unique('staff')}@brightloop.com"
        r = client.post(f"{API}/admin/staff", headers=admin,
                        json={"email": email, "full_name": "Staff Member", "password": PASSWORD, "role": role})
        assert r.status_code == 201, r.text
        return login_headers(client, email, PASSWORD)
    return _make


@pytest.fixture
def customer(client):
    email = f"{unique('cust')}@example.com"
    r = client.post(f"{API}/auth/signup", json={"email": email, "full_name": "Test Customer", "password": PASSWORD})
    assert r.status_code == 201, r.text
    return {"id": r.json()["id"], "email": email,
            "headers": login_headers(client, email, PASSWORD)}


@pytest.fixture
def catalog(client, admin):
    tax = client.post(f"{API}/catalog/taxes", headers=admin,
                      json={"name": unique("VAT"), "rate": 10}).json()
    product = client.post(f"{API}/catalog/products", headers=admin, json={
        "name": unique("Suite"), "product_type": "software", "sales_price": 100,
        "cost_price": 40, "tax_id": tax["id"]}).json()
    plan = client.post(f"{API}/catalog/plans", headers=admin, json={
        "name": unique("Monthly"), "product_id": product["id"], "price": 100,
        "billing_period": "monthly", "min_quantity": 1, "available_from": "2025-01-01",
        "end_behavior": "auto_close"}).json()
    return {"tax": tax, "product": product, "plan": plan}


@pytest.fixture
def activate(client, admin, catalog):
    """Creates a subscription for a customer and walks it to Active."""
    def _activate(cust, start="2026-01-01", expiry="2026-12-31", quantity=1, **extra):
        body = {"customer_id": cust["id"], "plan_id": catalog["plan"]["id"], "quantity": quantity,
                "start_date": start, "expiry_date": expiry, **extra}
        r = client.post(f"{API}/subscriptions", json=body, headers=admin)
        assert r.status_code == 201, r.text
        sub = r.json()
        for target in ("quotation", "confirmed", "active"):
            r = client.post(f"{API}/subscriptions/{sub['id']}/transition", json={"status": target}, headers=admin)
            assert r.status_code == 200, r.text
        return r.json()
    return _activate
