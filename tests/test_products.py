from tests.helpers import API, PASSWORD, login_headers, unique


def test_product_create_keeps_type_and_notes(client, admin):
    r = client.post(f"{API}/catalog/products", headers=admin, json={
        "name": unique("Ledger"), "product_type": "software", "sales_price": 499,
        "cost_price": 120, "notes": "Includes 12 months of support"})
    assert r.status_code == 201
    body = r.json()
    assert body["product_type"] == "software"
    assert body["notes"] == "Includes 12 months of support"


def test_product_defaults_when_type_and_notes_omitted(client, admin):
    body = client.post(f"{API}/catalog/products", headers=admin, json={
        "name": unique("Plain"), "sales_price": 10}).json()
    assert body["product_type"] == "service"
    assert body["notes"] is None


def test_products_without_notes_are_listed(client, admin):
    client.post(f"{API}/catalog/products", headers=admin, json={"name": unique("NoNotes"), "sales_price": 5})
    items = client.get(f"{API}/catalog/products", headers=admin).json()
    assert any(p["notes"] is None for p in items)


def test_product_update_changes_type_and_notes(client, admin):
    pid = client.post(f"{API}/catalog/products", headers=admin, json={
        "name": unique("Editable"), "sales_price": 100, "notes": "old"}).json()["id"]
    r = client.patch(f"{API}/catalog/products/{pid}", headers=admin,
                     json={"product_type": "hardware", "notes": "new note"})
    assert r.status_code == 200
    body = r.json()
    assert body["product_type"] == "hardware" and body["notes"] == "new note"
    assert float(body["sales_price"]) == 100.0            # untouched fields are preserved


def test_product_update_can_clear_notes(client, admin):
    pid = client.post(f"{API}/catalog/products", headers=admin, json={
        "name": unique("Clearable"), "sales_price": 1, "notes": "temporary"}).json()["id"]
    body = client.patch(f"{API}/catalog/products/{pid}", headers=admin, json={"notes": None}).json()
    assert body["notes"] is None


def test_product_update_rejects_empty_required_fields(client, admin):
    pid = client.post(f"{API}/catalog/products", headers=admin, json={
        "name": unique("Strict"), "sales_price": 1}).json()["id"]
    assert client.patch(f"{API}/catalog/products/{pid}", headers=admin,
                        json={"product_type": None}).status_code == 422
    assert client.patch(f"{API}/catalog/products/{pid}", headers=admin,
                        json={"sales_price": None}).status_code == 422


def test_product_update_is_admin_only(client, admin, make_staff):
    pid = client.post(f"{API}/catalog/products", headers=admin, json={
        "name": unique("Guarded"), "sales_price": 1}).json()["id"]
    assert client.patch(f"{API}/catalog/products/{pid}", headers=make_staff("staff"),
                        json={"notes": "x"}).status_code == 403


def test_product_update_unknown_id_is_404(client, admin):
    assert client.patch(f"{API}/catalog/products/999999", headers=admin, json={"notes": "x"}).status_code == 404
