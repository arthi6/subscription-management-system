from tests.helpers import API, PASSWORD, unique


def test_password_policy_rules(client):
    base = {"email": f"{unique('pw')}@example.com", "full_name": "Pw Test"}
    too_short = client.post(f"{API}/auth/signup", json={**base, "password": "Strong#1"})      # 8 chars
    no_upper = client.post(f"{API}/auth/signup", json={**base, "password": "strong#pass1"})
    no_special = client.post(f"{API}/auth/signup", json={**base, "password": "StrongPass1"})
    assert too_short.status_code == 422
    assert no_upper.status_code == 422
    assert no_special.status_code == 422
    ok = client.post(f"{API}/auth/signup", json={**base, "password": "Strong#Pass"})          # 11 chars
    assert ok.status_code == 201


def test_email_is_unique(client, customer):
    r = client.post(f"{API}/auth/signup", json={"email": customer["email"], "full_name": "Dup",
                                                "password": PASSWORD})
    assert r.status_code == 409


def test_only_admin_can_create_staff(client, admin, make_staff):
    staff_headers = make_staff("staff")
    payload = {"email": f"{unique('new')}@brightloop.com", "full_name": "New Hire", "password": PASSWORD}
    assert client.post(f"{API}/admin/staff", json=payload, headers=staff_headers).status_code == 403
    assert client.post(f"{API}/admin/staff", json=payload, headers=admin).status_code == 201


def test_roles_are_enforced_on_catalog(client, customer, make_staff):
    body = {"name": unique("VAT"), "rate": 5}
    assert client.post(f"{API}/catalog/taxes", json=body, headers=customer["headers"]).status_code == 403
    assert client.post(f"{API}/catalog/taxes", json=body, headers=make_staff("staff")).status_code == 403


def test_password_reset_link_is_single_use(client, customer, monkeypatch):
    sent = []
    monkeypatch.setattr("app.routers.auth.mailer.send_email", lambda to, subject, body: sent.append(body))
    client.post(f"{API}/auth/forgot-password", json={"email": customer["email"]})
    link = sent[-1].split()[-1]
    token = link.split("token=")[1]

    new_password = "Brand#New1"
    assert client.post(f"{API}/auth/reset-password",
                       json={"token": token, "new_password": new_password}).status_code == 200
    assert client.post(f"{API}/auth/reset-password",
                       json={"token": token, "new_password": "Another#Pass9"}).status_code == 400
    login = client.post(f"{API}/auth/login", json={"email": customer["email"], "password": new_password})
    assert login.status_code == 200


def test_forgot_password_does_not_reveal_accounts(client):
    r = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@nowhere.example"})
    assert r.status_code == 202
