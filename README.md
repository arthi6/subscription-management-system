# Subscription Management System

A full-stack subscription and billing management application designed to simplify subscription lifecycles, recurring billing, invoice generation, payment tracking, and financial reporting.

The project uses **FastAPI, React, and PostgreSQL** to provide a structured solution for managing subscription-based business operations.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Security](#security)
- [Limitations](#limitations)
- [Future Enhancements](#future-enhancements)
- [Author](#author)

## Overview

Managing subscription-based services requires accurate handling of customers, subscription plans, billing cycles, invoices, payments, renewals, and outstanding balances.

The Subscription Management System centralizes these operations in a single application.

The backend provides APIs for managing subscriptions, processing recurring billing, generating invoices, recording payments, and retrieving financial reports. The frontend provides an interface for administrators, staff, and customers to access the functionality available to their roles.

The application focuses on maintaining consistent business rules, protecting customer data, and preventing common billing errors.

## Key Features

### 1. Subscription Lifecycle Management

- Create and manage products, product variants, and subscription plans.
- Manage subscriptions and quotation-based subscription workflows.
- Track subscription statuses and lifecycle transitions.
- Configure subscription expiry and renewal behaviour.
- Maintain subscription status history.
- Support administrative subscription management.

### 2. Recurring Billing

- Generate invoices for eligible subscriptions.
- Handle missed billing periods during recurring billing runs.
- Prevent duplicate invoices for the same subscription and billing period.
- Record billing-run results and errors.
- Track billing operations for monitoring and troubleshooting.

### 3. Invoice Management

- Generate invoices for subscription billing.
- Calculate applicable taxes and discounts.
- Confirm and cancel invoices.
- Send invoices through the configured email service.
- Generate print-ready invoice views.
- Track outstanding and overdue invoice balances.
- Support payment reminders.

### 4. Payment Management

- Record payments against invoices.
- Track paid amounts and remaining balances.
- Validate payments against the outstanding invoice amount.
- Store payment details, including payment method, date, amount, and notes.
- Maintain payment records for financial tracking.

### 5. Discounts and Taxes

- Manage applicable tax configurations.
- Apply supported fixed-value and percentage-based discounts.
- Calculate invoice totals based on the applicable tax and discount rules.
- Maintain consistent billing calculations.

### 6. Dashboard and Financial Reporting

- View subscription and financial metrics.
- Monitor collected revenue and outstanding balances.
- Track overdue invoices.
- Retrieve financial summaries.
- Filter and paginate supported records.

### 7. Authentication and Role-Based Access Control

- JWT-based authentication.
- Role-based authorization for administrators, staff, and customers.
- Password hashing using bcrypt.
- Time-limited password-reset workflow.
- Customer-specific access to subscriptions and invoices.
- Protected API endpoints based on user permissions.

### 8. Web Interface

- React-based frontend powered by Vite.
- Dashboard for subscription and financial information.
- Interfaces for managing customers, products, plans, subscriptions, and invoices.
- Customer portal for accessing personal subscription and invoice information.
- API integration between the frontend and backend.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python 3.12 |
| Backend Framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Data Validation | Pydantic v2 |
| Database | PostgreSQL 16 |
| Authentication | JWT |
| Password Hashing | bcrypt |
| Frontend Framework | React 18 |
| Frontend Build Tool | Vite |
| Testing Framework | Pytest |
| Containerization | Docker |
| Email Testing | Mailpit |
| API Documentation | Swagger UI, ReDoc |

## System Architecture

The Subscription Management System follows a modular, layered architecture that separates the presentation layer, API layer, business logic, and data storage. This separation improves maintainability, security, and scalability.

```text
┌──────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                      │
│                                                              │
│                 React 18 + Vite Frontend                     │
│                                                              │
│   Admin Dashboard  │  Staff Interface  │  Customer Portal    │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              │ HTTP / REST API
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                       API LAYER                              │
│                                                              │
│                       FastAPI                                │
│                                                              │
│   Authentication  │  Request Validation  │  Authorization   │
│                                                              │
│   Routers: Auth, Products, Plans, Subscriptions, Invoices,   │
│            Payments, Billing, Reports, Customer Portal       │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                     BUSINESS LOGIC LAYER                     │
│                                                              │
│   Subscription Lifecycle Management                          │
│   Recurring Billing and Invoice Generation                   │
│   Tax and Discount Calculations                              │
│   Payment Validation and Balance Tracking                    │
│   Financial Reporting and Billing-Run Management             │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      DATA ACCESS LAYER                       │
│                                                              │
│                  SQLAlchemy 2.0 ORM                          │
│                                                              │
│      Database Models  │  Relationships  │  Constraints       │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              │ SQL Queries
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                       DATA LAYER                             │
│                                                              │
│                       PostgreSQL                             │
│                                                              │
│   Customers │ Products │ Plans │ Subscriptions │ Invoices    │
│                  Payments │ Billing Records                  │
└──────────────────────────────────────────────────────────────┘


                    SUPPORTING SERVICES

       ┌────────────────────┐  ┌────────────────────────┐
       │ JWT Authentication │  │ Mailpit Email Testing  │
       │ Password Security  │  │ SMTP / Email Preview   │
       └────────────────────┘  └────────────────────────┘
```

### Architecture Components

| Layer | Responsibility | Technologies |
|---|---|---|
| Presentation | Provides interfaces for administrators, staff, and customers | React, Vite |
| API | Exposes REST endpoints and handles request validation and access control | FastAPI, Pydantic |
| Business Logic | Manages subscriptions, billing, invoices, payments, and reports | Python service modules |
| Data Access | Maps application objects to database records and manages database operations | SQLAlchemy |
| Data Storage | Persists customer, subscription, invoice, and payment records | PostgreSQL |
| Supporting Services | Provides authentication mechanisms and local email testing | JWT, bcrypt, Mailpit |

### Request Flow

1. A user interacts with the React frontend.
2. The frontend sends an HTTP request to the FastAPI backend.
3. The backend validates the request and checks authentication and authorization requirements.
4. The appropriate service executes the relevant business rules.
5. SQLAlchemy interacts with PostgreSQL to retrieve or update records.
6. The backend returns the response to the frontend.
7. The frontend displays the result to the user.

**Design principle:** Separating API endpoints, business logic, and database operations keeps the application modular and makes its subscription and billing workflows easier to maintain and test.

### Backend Components

- **Routers:** Handle HTTP requests and API responses.
- **Services:** Implement subscription, billing, payment, and reporting logic.
- **Models:** Define database entities, relationships, constraints, and indexes.
- **Schemas:** Validate incoming data and structure API responses.
- **Security:** Manage authentication, password hashing, and authorization.
- **Database Layer:** Provides database connectivity and session management.

## Project Structure

The main project structure is organized as follows:

```text
subscription-management-system/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── security.py
│   ├── deps.py
│   ├── routers/
│   └── services/
│
├── frontend/
├── scripts/
├── tests/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

**Note:** This structure highlights the main application components. Refer to the repository for the complete directory and file listing.

## Prerequisites

Install the following tools before running the application:

- Python 3.12
- Node.js and npm
- Docker Desktop with Docker Compose
- Git

The application can also use a locally installed PostgreSQL database if its connection settings are configured correctly.

## Installation and Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/arthi6/subscription-management-system.git
```

Navigate to the project directory:

```bash
cd subscription-management-system
```

### Step 2: Configure Environment Variables

Create a local environment file from the example configuration.

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure the required database connection details, authentication secrets, email settings, and administrator settings.

Use the variable names defined in `.env.example`.

**Important:** Never commit `.env` or expose passwords, JWT secrets, or production credentials in your repository.

### Step 3: Start the Database and Email Testing Services

If you are using the project's Docker Compose configuration, start PostgreSQL and Mailpit:

```bash
docker compose up -d db mailpit
```

Check the service status:

```bash
docker compose ps
```

The configured local service endpoints are:

| Service | Address |
|---|---|
| PostgreSQL | `localhost:5437` |
| Mailpit Web Interface | `http://localhost:8026` |
| Mailpit SMTP | `localhost:1026` |

**Connection details:** The PostgreSQL container listens on port `5432` internally and maps to host port `5437`. When the backend runs directly on your computer, use the host port. When it runs inside the same Docker network, use the database service name and internal port.

Mailpit captures development emails so you can inspect messages without sending them to real recipients.

### Step 4: Create a Python Virtual Environment

From the project root, run the following commands in Windows PowerShell:

```powershell
py -3.12 -m venv .venv
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip and install the dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Ensure that the virtual environment is activated before running the backend or tests.

### Step 5: Start the Backend

From the project root, run:

```powershell
uvicorn app.main:app --reload --port 8000
```

The backend will be available at:

- **API Base URL:** `http://localhost:8000`
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

Make sure the database is running and the environment variables are correctly configured before starting the application.

## Running the Application

### Start the Frontend

Open a second terminal and navigate to the frontend directory:

```powershell
cd frontend
```

Install the dependencies:

```powershell
npm install
```

Start the development server:

```powershell
npm run dev
```

Open the URL displayed in the terminal by Vite.

Ensure that the frontend API configuration points to the correct backend address.

### Build the Frontend

To create a production build, run:

```powershell
npm run build
```

### Run the Application Using Docker Compose

If your Docker Compose configuration includes all the required application services, you can build and start them with:

```bash
docker compose up -d --build
```

Check running services:

```bash
docker compose ps
```

View service logs:

```bash
docker compose logs -f
```

Stop the services:

```bash
docker compose down
```

Stopping the containers does not normally delete named database volumes. Use `docker compose down -v` only when you intentionally want to delete the associated volumes and their stored data.

## API Documentation

The backend uses FastAPI to expose APIs for the application's main business operations.

Interactive API documentation is available at:

`http://localhost:8000/docs`

The alternative documentation interface is available at:

`http://localhost:8000/redoc`

### Main API Modules

| Module | Description |
|---|---|
| Authentication | User authentication and password-reset operations |
| Staff Management | Administrative staff operations |
| Products and Plans | Product, variant, and subscription-plan management |
| Subscriptions | Subscription creation and lifecycle management |
| Billing | Recurring billing runs and billing history |
| Invoices | Invoice generation and invoice operations |
| Payments | Payment recording and balance tracking |
| Reports | Financial summaries and subscription metrics |
| Customer Portal | Customer-specific subscription and invoice access |

The exact endpoints, request parameters, response schemas, and authorization requirements are available in Swagger UI.

## Testing

The project uses Pytest for backend testing.

Activate the Python virtual environment and run the test suite from the project root:

```powershell
pytest -q
```

Review the output to identify failed tests and confirm that the current implementation behaves as expected.

To validate the frontend build, navigate to the frontend directory and run:

```powershell
npm run build
```

Only report a test count or success rate after confirming the result against the exact version of the code you intend to publish.

## Security

The application includes several security-related mechanisms:

- JWT-based authentication.
- Role-based authorization.
- Password hashing using bcrypt.
- Time-limited password-reset tokens.
- Customer-specific access restrictions.
- Database constraints for preventing duplicate billing-period invoices.
- Validation of payment amounts against outstanding balances.

### Production Security Considerations

Before deploying the application to production:

- Use strong, unique authentication secrets.
- Enable HTTPS.
- Restrict database access.
- Configure production email delivery.
- Protect administrator accounts and credentials.
- Review environment variables and access permissions.
- Configure appropriate logging, monitoring, and backups.

The local development configuration should not be treated as a complete production deployment configuration.

## Limitations

The current implementation has areas that could be improved:

- A dedicated database migration workflow would improve schema-change management.
- Invoice printing uses print-ready HTML rather than a dedicated server-generated PDF endpoint.
- Explicit multi-currency support could be added.
- Frontend automated testing could be expanded.
- Large recurring-billing workloads would benefit from additional performance testing.
- Background-job processing and operational monitoring could be expanded as the application grows.

These limitations should be reviewed against the latest code before publishing a release.

## Future Enhancements

Potential future improvements include:

- Introducing database migrations using Alembic.
- Expanding automated frontend and end-to-end testing.
- Implementing dedicated invoice PDF generation and downloads.
- Adding explicit currency support.
- Improving financial analytics and reporting.
- Introducing scalable background-job processing for recurring billing.
- Expanding application monitoring and performance metrics.
- Improving deployment automation and production observability.

GitHub Repository:  
https://github.com/arthi6/subscription-management-system
