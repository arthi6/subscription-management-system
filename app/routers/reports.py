from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Role, User
from app.services import reports as report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
def finance_summary(
    start: Optional[date] = Query(None, description="Defaults to the first day of this month"),
    end: Optional[date] = Query(None, description="Defaults to today"),
    plan_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    _user: User = Depends(require_roles(Role.admin, Role.staff)),
    db: Session = Depends(get_db),
):
    today = date.today()
    return report_service.summary(db, start or today.replace(day=1), end or today, plan_id, customer_id)
