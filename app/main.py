import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import models  # noqa: F401  registers every table with Base.metadata
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.errors import DomainError
from app.models import Role, User
from app.routers import auth, catalog, invoices, portal, reports, subscriptions
from app.security import hash_password
from app.services.billing import run_billing

log = logging.getLogger("billing")


def bootstrap_admin() -> None:
    """Creates the first admin account on an empty database. Only admins can create staff."""
    with SessionLocal() as db:
        exists = db.scalar(select(User.id).where(User.role == Role.admin))
        if exists is None:
            db.add(User(email=settings.bootstrap_admin_email.lower(), full_name="System Administrator",
                        password_hash=hash_password(settings.bootstrap_admin_password), role=Role.admin))
            db.commit()
            log.info("Bootstrap admin created: %s", settings.bootstrap_admin_email)


async def billing_scheduler() -> None:
    while True:
        await asyncio.sleep(settings.billing_interval_seconds)
        def _run():
            with SessionLocal() as db:
                return run_billing(db, date.today())
        run = await asyncio.to_thread(_run)
        log.info("Scheduled billing run: %s invoices created", run.invoices_created)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)  # use Alembic migrations for real deployments
    bootstrap_admin()
    task = asyncio.create_task(billing_scheduler()) if settings.billing_auto_run else None
    yield
    if task:
        task.cancel()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url],
                   allow_methods=["*"], allow_headers=["*"], allow_credentials=True)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_request: Request, _exc: IntegrityError):
    # Database constraints are the last line of defence (unique emails, one invoice per period, etc.)
    return JSONResponse(status_code=409, content={"detail": "This change conflicts with existing data"})


PREFIX = "/api/v1"
for module in (auth, catalog, subscriptions, invoices, reports, portal):
    app.include_router(module.router, prefix=PREFIX)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "app": settings.app_name}
