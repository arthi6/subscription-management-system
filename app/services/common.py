from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from dateutil.relativedelta import relativedelta
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import BillingPeriod

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def D(value) -> Decimal:
    """Convert any numeric (Decimal, int, float, str) to Decimal without float artefacts."""
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)


def sum_money(values: Iterable) -> Decimal:
    return sum((D(v) for v in values), ZERO)


def add_period(start: date, period: BillingPeriod) -> date:
    if period == BillingPeriod.daily:
        return start + timedelta(days=1)
    if period == BillingPeriod.weekly:
        return start + timedelta(days=7)
    if period == BillingPeriod.monthly:
        return start + relativedelta(months=1)
    return start + relativedelta(years=1)


def paginate(db: Session, stmt: Select, page: int, page_size: int) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return {"page": page, "page_size": page_size, "total": total, "items": rows}
