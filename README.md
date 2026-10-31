# Subscription Management System (Brightloop Software)

A backend platform that runs the full life of a subscription business: products and variants,
plans, taxes, discounts, quotation templates, subscriptions with a controlled lifecycle,
automatic billing with exactly-once invoicing, payments, overdue tracking, and finance reporting.

Stack: **Python 3.12 · FastAPI · SQLAlchemy 2.0 · PostgreSQL 16 · Pydantic v2 · JWT · bcrypt · Pytest**

---

## 1. Abstract

Brightloop Software sells on subscription, so its revenue arrives every month rather than once.
Today its subscriptions live in a spreadsheet, invoices are typed by hand, payments are matched by
scrolling through bank statements, and renewals are remembered by whoever notices first. This
project replaces that process with one system of record.

The backend is a modular FastAPI service over PostgreSQL. The data model enforces integrity in the
database itself: one invoice per subscription per billing period is a unique constraint, lifecycle
states are checked by a transition table, and payments are validated against outstanding balances
inside row-locked transactions. The billing engine runs as a batch that catches up missed periods,
is idempotent, isolates failures per subscription, and records every failure in a run log. Discount
usage limits are enforced with an atomic conditional update, so concurrent runs cannot exceed them.

Access is role-based (admin, staff, customer). Passwords are stored as bcrypt hashes and password
reset tokens as SHA-256 hashes, single-use and time-limited. Customers see only their own data through
the portal endpoints, and a request for another customer's record returns 404 rather than revealing
that it exists. Reports are computed with SQL aggregates and indexed filters, so dashboards stay
within the two-second target on large books of business.

---

## 2. Requirement coverage

| Scene in the brief | Where it is implemented |
|---|---|
| Sign up with unique email; strong passwords | `schemas.check_password`, `auth.signup`, unique index on `users.email` |
| Password reset link by email | `auth.forgot_password`, `auth.reset_password` (single use, 30-minute expiry) |
| Admin / staff / customer access | `deps.require_roles`; only admin can call `POST /admin/staff` |
| Products, sales and cost price | `catalog.create_product` |
| Variants that add to price (e.g. Odoo brand +560) | `catalog.add_variant`, applied in `subscriptions.create_subscription` |
| Plans with billing period, min quantity, availability dates | `catalog.create_plan`, enforced on subscription creation |
| Plan end behaviour: auto-close, manual close, pause, renew | `EndBehavior` handling in `billing.bill_subscription` |
| Quotation templates with validity in days | `catalog.create_template`, `subscriptions.create_from_template` |
| Subscription number, lines, expiry, payment terms | `Subscription`, `SubscriptionLine`, `create_subscription` |
| Draft → Quotation → Confirmed → Active → Closed, logged | `subscriptions.ALLOWED_TRANSITIONS`, `SubscriptionStatusLog` |
| Taxes calculated automatically | `Tax` linked to products; computed per line in `billing.build_invoice` |
| Automatic invoices on billing day, nothing billed twice or skipped | `billing.run_billing`, unique `(subscription_id, period_start)` |
| Invoice Draft → Confirmed → Paid; confirm, cancel, send, print | `invoices` router, `billing.confirm_invoice` / `cancel_invoice` |
| Discounts: fixed or percent, min purchase/quantity, dates, usage limit | `Discount` model, `billing._find_discount`, `_consume_usage` |
| Discount applies to next invoice automatically and stops when used up | Applied in every `build_invoice`; atomic usage counter |
| Payments by method, amount, date, note, against an invoice | `payments` service, `POST /invoices/{id}/payments` |
| Paid vs outstanding; overdue chasing | `invoices?overdue=true`, `POST /invoices/reminders` |
| Finance summary: active subs, revenue, outstanding, overdue, filters | `GET /reports/summary` with date, plan and customer filters |
| Pages respond under two seconds with thousands of subscriptions | Indexes, server-side pagination, SQL aggregates, `scripts/seed.py` |

---

## 3. Architecture

```
app/
  main.py            FastAPI app, lifespan (create tables, bootstrap admin, optional scheduler),
                     exception handlers (domain errors → 422, integrity errors → 409)
  config.py          Settings from environment variables / .env
  database.py        Engine, session factory, get_db, utcnow; SQLite FK pragma for tests
  models.py          SQLAlchemy 2.0 models, enums, constraints, indexes
  schemas.py         Pydantic request models and password policy
  security.py        bcrypt, JWT, reset token generation
  deps.py            get_current_user, require_roles, get_or_404
  mailer.py          SMTP sender (Mailpit locally); logs instead of failing if SMTP is down
  serializers.py     Response shaping
  services/          Business rules, free of HTTP concerns
    subscriptions.py   State machine, subscription creation
    billing.py         Invoice building, discounts, taxes, billing runs, invoice actions
    payments.py        Payment recording and derived invoice status
    reports.py         Finance aggregates and aging buckets
    common.py          Decimal helpers, period arithmetic, pagination
  routers/           Thin HTTP layer: auth, catalog, subscriptions, invoices, reports, portal
tests/               Pytest suite (18 tests) run against SQLite
scripts/seed.py      Demo data generator for performance checks
```

Routers only parse input and call services. All rules live in `services/`, which is what makes the
billing logic testable and easy to explain in a review.

### Data model (key relationships)

```
users ──< subscriptions >── plans >── products ──< product_variants
              │   │                      │
              │   └──< subscription_lines >── taxes
              │   └──< subscription_status_logs
              │   └── discounts (optional, per subscription)
              │
              └──< invoices ──< invoice_lines
                     │   UNIQUE (subscription_id, period_start)
                     └──< payments

billing_runs            run log with per-subscription errors
password_reset_tokens   SHA-256 hashes only, single use
```

Money is `NUMERIC(12,2)` and is rounded half-up with `Decimal` in Python. Floats are never used for
amounts.

---

## 4. Billing rules, precisely

1. **Which subscriptions are billed:** only `active` subscriptions whose `next_billing_date` is on or
   before the run date. Draft, quotation, confirmed and closed subscriptions are never billed.
2. **One invoice per period:** each period is `[period_start, period_end]`, where the length follows the
   plan's billing period (daily, weekly, monthly or yearly). Before creating an invoice the engine
   checks for an existing one, and the unique constraint in the database is the final guarantee.
3. **Catch-up:** if the run date is months after the last run, every missed period is billed in order.
4. **Expiry:** the engine never bills a period that starts on or after `expiry_date`, except for `renew`.
   - `auto_close`: the subscription is closed when its expiry is reached.
   - `manual_close`: billing stops; an admin closes the subscription.
   - `pause`: billing stops; an admin extends `expiry_date` through `PATCH /subscriptions/{id}/expiry`
     to resume.
   - `renew`: expiry is extended one period at a time and billing continues.
5. **Discounts:** a discount applies to the invoice for each period while it is active by date and while
   its usage counter is below the limit. Each use increments the counter atomically. Product-scoped
   discounts apply to matching lines only. Subscription-scoped discounts are spread across lines in
   proportion to their value, with rounding absorbed by the last line, so the parts always sum to the
   discount. Cancelling an invoice returns its discount use.
6. **Taxes:** each line's tax is `(subtotal − discount) × rate`, rounded to cents. Invoice totals are sums of
   the line values.
7. **Failures:** each subscription is billed inside its own savepoint. A failure is rolled back for that
   subscription only, recorded in `billing_runs.errors`, and the run continues.

---

## 5. Security

- Passwords are hashed with bcrypt (cost 12). The policy is more than 8 characters, with an uppercase
  letter, a lowercase letter and a special character.
- JWT access tokens expire after `ACCESS_TOKEN_MINUTES` (default 60).
- Reset tokens are random 256-bit values. Only their SHA-256 hash is stored. They expire after 30
  minutes, can be used once, and all of a user's outstanding tokens are burned when one is used.
- `forgot-password` returns the same response whether or not the account exists.
- Role checks run on every route. A customer calling a staff route receives 403. A customer asking for
  another customer's subscription or invoice receives 404.
- Payments take a row lock (`SELECT … FOR UPDATE` on PostgreSQL) so concurrent payments cannot overpay an invoice.

---

## 6. Deployment on your local machine

There are two ways to run this. **Option A** runs the database in Docker and the API on your machine,
which is the best choice for development and demos. **Option B** runs everything in Docker with one
command. Both assume you are in the project folder, the one that contains `app/` and `docker-compose.yml`.

### Prerequisites

| Tool | Check it works | Install |
|---|---|---|
| Python 3.12 (3.11+ also works) | `python3 --version` | python.org, or `brew install python@3.12` on macOS |
| Docker Desktop (Docker Engine plus the Compose plugin on Linux) | `docker --version` and `docker compose version` | docker.com |
| Git (optional) | `git --version` | git-scm.com |

On Windows, run the commands below in PowerShell. Where a command differs, the Windows version is shown.

### Step 1: Unzip the project

```bash
unzip subscription-system.zip
cd subscription-system
```

### Step 2: Create your environment file

```bash
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
```

Open `.env` and change `JWT_SECRET` to a long random string. Leave the rest as it is for local use.

---

### Option A: Database in Docker, API on your machine (recommended)

**A1. Start PostgreSQL and the mail catcher**

```bash
docker compose up -d db mailpit
docker compose ps        # db should show "healthy" after a few seconds
```

- PostgreSQL runs on `localhost:5432` (user `subs`, password `subs`, database `subscriptions`).
- Mailpit's inbox is at **http://localhost:8025**. Reset links and invoice emails appear there.

**A2. Create a virtual environment and install dependencies**

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**A3. Start the API**

```bash
uvicorn app.main:app --reload --port 8000
```

On first start the app creates every table and the bootstrap admin account:
`admin@brightloop.com` / `Admin@12345` (from `.env`). You will see
`Bootstrap admin created` in the log.

**A4. Check that it works**

- Health: http://localhost:8000/health should return `{"status":"ok",...}`
- Interactive API docs: **http://localhost:8000/docs**. Use the "Authorize" button with the bearer
  token from the login step below.

---

### Option B: Everything in Docker

```bash
docker compose up -d --build
docker compose logs -f api        # wait for "Application startup complete"
```

- API: http://localhost:8000/docs
- Mail inbox: http://localhost:8025

To stop: `docker compose down`. To also delete the database volume: `docker compose down -v`.

---

### Step 3: Run the tests

With the virtual environment active:

```bash
pytest -q
```

Expected output: `18 passed`. The tests use a separate SQLite file (`test_subscriptions.db`) and do not
touch your PostgreSQL data.

---

### Step 4: Walk through one billing month (copy and paste)

These commands use `curl`, which is included on macOS, Linux and Windows 10/11. Each block builds on the
previous one. For Windows, use Git Bash or WSL, or do the same steps in the `/docs` page.

**4.1 Log in as admin and save the token**

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@brightloop.com","password":"Admin@12345"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "$TOKEN" | head -c 20 && echo
```

**4.2 Create a tax, a product and a plan**

```bash
curl -s -X POST localhost:8000/api/v1/catalog/taxes -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name":"GST 18%","rate":18}'

curl -s -X POST localhost:8000/api/v1/catalog/products -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Odoo Business Suite","product_type":"software","sales_price":999,"cost_price":400,"tax_id":1}'

curl -s -X POST localhost:8000/api/v1/catalog/products/1/variants -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"attribute":"brand","value":"Odoo","price_extra":560}'

curl -s -X POST localhost:8000/api/v1/catalog/plans -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Monthly Standard","product_id":1,"price":999,"billing_period":"monthly","min_quantity":1,"available_from":"2025-01-01","end_behavior":"renew"}'
```

**4.3 Create a customer account (self sign-up) and a discount**

```bash
curl -s -X POST localhost:8000/api/v1/auth/signup -H "Content-Type: application/json" \
  -d '{"email":"acme@example.com","full_name":"Acme Ltd","password":"Acme#Pass123"}'

curl -s -X POST localhost:8000/api/v1/catalog/discounts -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Seat promo","kind":"percent","value":10,"scope":"subscription","start_date":"2026-01-01","usage_limit":3}'
```

Note the returned customer `id` (usually `2`) and discount `id` (usually `1`).

**4.4 Create a subscription, then move it to Active**

```bash
SUB=$(curl -s -X POST localhost:8000/api/v1/subscriptions -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":2,"plan_id":1,"quantity":5,"start_date":"2026-01-01","expiry_date":"2026-12-31","variant_ids":[1],"discount_id":1}')
SUB_ID=$(echo "$SUB" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "$SUB" | python3 -m json.tool | head -20

for S in quotation confirmed active; do
  curl -s -X POST localhost:8000/api/v1/subscriptions/$SUB_ID/transition -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" -d "{\"status\":\"$S\"}" > /dev/null
done
echo "subscription $SUB_ID is now active"
```

**4.5 Run billing day**

```bash
curl -s -X POST "localhost:8000/api/v1/billing/runs?run_date=2026-03-15" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: `invoices_created: 3` (January, February, March). Run the same command again and it
returns `invoices_created: 0`. That is the exactly-once guarantee.

**4.6 Confirm an invoice, send it, and record a payment**

```bash
INV_ID=$(curl -s "localhost:8000/api/v1/invoices?customer_id=2" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json;print(sorted(json.load(sys.stdin)['items'],key=lambda i:i['period_start'])[0]['id'])")

curl -s -X POST localhost:8000/api/v1/invoices/$INV_ID/confirm -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -12
curl -s -X POST localhost:8000/api/v1/invoices/$INV_ID/send -H "Authorization: Bearer $TOKEN" > /dev/null   # check http://localhost:8025

curl -s -X POST localhost:8000/api/v1/invoices/$INV_ID/payments -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"method":"bank_transfer","amount":500,"paid_on":"2026-01-20","note":"UTR 123456"}'
curl -s -X POST localhost:8000/api/v1/invoices/$INV_ID/payments -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"method":"upi","amount":100000,"paid_on":"2026-01-21"}'   # rejected: over balance
```

**4.7 Finance summary and the customer's own view**

```bash
curl -s "localhost:8000/api/v1/reports/summary?start=2026-01-01&end=2026-03-31" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

CUST=$(curl -s -X POST localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"email":"acme@example.com","password":"Acme#Pass123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s localhost:8000/api/v1/portal/subscriptions -H "Authorization: Bearer $CUST" | python3 -m json.tool | head -20
```

**4.8 Forgot password flow**

```bash
curl -s -X POST localhost:8000/api/v1/auth/forgot-password -H "Content-Type: application/json" \
  -d '{"email":"acme@example.com"}'
```

Open http://localhost:8025, find the email, and copy the link. Then:

```bash
curl -s -X POST localhost:8000/api/v1/auth/reset-password -H "Content-Type: application/json" \
  -d '{"token":"PASTE_TOKEN_HERE","new_password":"Brand#New123"}'
```

---

### Step 5: Load realistic volume and check performance

With the API stopped (or in a second terminal, with the venv active):

```bash
python -m scripts.seed --customers 5000
```

This creates 5,000 active subscriptions in about a minute. Then time the pages that matter:

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@brightloop.com","password":"Admin@12345"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -o /dev/null -w "subscriptions list: %{time_total}s\n" \
  "localhost:8000/api/v1/subscriptions?status=active&page=1&page_size=50" -H "Authorization: Bearer $TOKEN"
curl -s -o /dev/null -w "finance summary:    %{time_total}s\n" \
  "localhost:8000/api/v1/reports/summary" -H "Authorization: Bearer $TOKEN"
curl -s -o /dev/null -w "overdue invoices:   %{time_total}s\n" \
  "localhost:8000/api/v1/invoices?overdue=true" -H "Authorization: Bearer $TOKEN"
```

Seeded customers all use the password `Seed@Pass1`. Seeding with a large count also creates large
catch-up backlogs when you run billing, so expect the first run to take longer. The large numbers are
for the performance check only.

---

### Optional: run billing automatically

Set `BILLING_AUTO_RUN=true` and `BILLING_INTERVAL_SECONDS=86400` in `.env`, then restart the API. The
app runs a billing pass every 24 hours in the background. The manual endpoint keeps working alongside it,
because billing is idempotent.

---

## 6a. Running the web console

The console is a separate React app in `frontend/`. Keep the API running (section 6), then in a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** and log in with `admin@brightloop.com` / `Admin@12345`. The dev server forwards
`/api` requests to the API on port 8000, so no CORS setup is needed. See `frontend/README.md` for screen-by-screen notes.

---

## 7. API overview

Base URL: `http://localhost:8000/api/v1`. Full interactive docs at `/docs`.

| Area | Endpoints | Roles |
|---|---|---|
| Auth | `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`, `POST /auth/forgot-password`, `POST /auth/reset-password` | public / any |
| Staff | `POST /admin/staff` | admin |
| Catalog | `/catalog/taxes`, `/catalog/products`, `/catalog/products/{id}/variants`, `/catalog/plans`, `/catalog/plans/{id}/close`, `/catalog/quotation-templates`, `/catalog/discounts` | writes admin; reads admin + staff |
| Subscriptions | `POST /subscriptions`, `POST /subscriptions/from-template/{id}`, `GET /subscriptions`, `GET /subscriptions/{id}`, `POST /subscriptions/{id}/transition`, `PATCH /subscriptions/{id}/expiry` | admin + staff |
| Billing | `POST /billing/runs?run_date=`, `GET /billing/runs` | admin + staff |
| Invoices | `GET /invoices`, `GET /invoices/{id}`, `POST /invoices/{id}/confirm`, `/cancel`, `/send`, `GET /invoices/{id}/print`, `POST /invoices/reminders` | admin + staff |
| Payments | `POST /invoices/{id}/payments`, `GET /invoices/{id}/payments` | admin + staff |
| Reports | `GET /reports/summary?start=&end=&plan_id=&customer_id=` | admin + staff |
| Portal | `GET /portal/subscriptions`, `GET /portal/subscriptions/{id}`, `GET /portal/invoices`, `GET /portal/invoices/{id}` | customer (own data only) |

List endpoints accept `page` and `page_size` (max 100) and return `{page, page_size, total, items}`.

---

## 8. Known limits and next steps

These are deliberate scope decisions. They are the first things to add if the project continues.

- **Migrations:** tables are created on startup with `create_all`. For production, add Alembic revisions.
- **PDF invoices:** `/invoices/{id}/print` returns plain text. A WeasyPrint or ReportLab renderer slots into
  the same route.
- **Frontend:** the brief asks for a working backend first, so this repository contains the API only. The
  `/docs` page is the admin console until a React front end is built against the same endpoints.
- **Cancelled periods:** a cancelled invoice keeps its period, so the engine will not bill that period again.
  A credit-note flow would be the next step for corrections.
- **Billing throughput:** the engine flushes one invoice at a time inside a savepoint per subscription.
  Catch-up runs over very large backlogs should be batched or run in parallel by shard.
- **Tests:** the suite covers the business rules and access control. Load tests should use the seed
  script against PostgreSQL.
