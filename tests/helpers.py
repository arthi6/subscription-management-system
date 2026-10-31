import uuid

API = "/api/v1"
PASSWORD = "Strong#Pass1"


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def login_headers(client, email: str, password: str) -> dict:
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def invoices_for(client, admin, customer_id):
    r = client.get(f"{API}/invoices", params={"customer_id": customer_id, "page_size": 100}, headers=admin)
    assert r.status_code == 200, r.text
    return sorted(r.json()["items"], key=lambda i: i["period_start"])
