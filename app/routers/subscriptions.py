from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_or_404, require_roles
from app.errors import DomainError
from app.models import Discount, Plan, QuotationTemplate, Role, Subscription, SubStatus, User
from app.schemas import ExpiryIn, FromTemplateIn, SubscriptionIn, TransitionIn
from app.serializers import sub_out
from app.services.common import paginate
from app.services.subscriptions import create_subscription, transition

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
ops = require_roles(Role.admin, Role.staff)


def _discount(db: Session, discount_id: Optional[int]) -> Optional[Discount]:
    return get_or_404(db, Discount, discount_id, "Discount") if discount_id else None


@router.post("", status_code=201)
def create(body: SubscriptionIn, user: User = Depends(ops), db: Session = Depends(get_db)):
    customer = get_or_404(db, User, body.customer_id, "Customer")
    plan = get_or_404(db, Plan, body.plan_id, "Plan")
    sub = create_subscription(
        db, customer=customer, plan=plan, quantity=body.quantity, start_date=body.start_date,
        expiry_date=body.expiry_date, variant_ids=body.variant_ids,
        discount=_discount(db, body.discount_id), payment_terms_days=body.payment_terms_days,
        actor_id=user.id,
    )
    return sub_out(sub, detail=True)


@router.post("/from-template/{template_id}", status_code=201)
def create_from_template(template_id: int, body: FromTemplateIn, user: User = Depends(ops),
                         db: Session = Depends(get_db)):
    template = get_or_404(db, QuotationTemplate, template_id, "Quotation template")
    if not template.is_active:
        raise DomainError("This quotation template is no longer active")
    customer = get_or_404(db, User, body.customer_id, "Customer")
    sub = create_subscription(
        db, customer=customer, plan=template.plan, quantity=body.quantity, start_date=body.start_date,
        expiry_date=body.expiry_date, variant_ids=body.variant_ids,
        discount=_discount(db, body.discount_id), template=template, actor_id=user.id,
    )
    return sub_out(sub, detail=True)


@router.get("")
def list_subscriptions(
    status_filter: Optional[SubStatus] = Query(None, alias="status"),
    plan_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: User = Depends(ops),
    db: Session = Depends(get_db),
):
    stmt = select(Subscription).order_by(Subscription.id.desc())
    if status_filter:
        stmt = stmt.where(Subscription.status == status_filter)
    if plan_id:
        stmt = stmt.where(Subscription.plan_id == plan_id)
    if customer_id:
        stmt = stmt.where(Subscription.customer_id == customer_id)
    result = paginate(db, stmt, page, page_size)
    result["items"] = [sub_out(s) for s in result["items"]]
    return result


@router.get("/{sub_id}")
def get_subscription(sub_id: int, _user: User = Depends(ops), db: Session = Depends(get_db)):
    return sub_out(get_or_404(db, Subscription, sub_id, "Subscription"), detail=True)


@router.post("/{sub_id}/transition")
def change_status(sub_id: int, body: TransitionIn, user: User = Depends(ops), db: Session = Depends(get_db)):
    sub = get_or_404(db, Subscription, sub_id, "Subscription")
    transition(db, sub, body.status, actor_id=user.id)
    db.commit()
    return sub_out(sub, detail=True)


@router.patch("/{sub_id}/expiry")
def change_expiry(sub_id: int, body: ExpiryIn, _user: User = Depends(ops), db: Session = Depends(get_db)):
    """Extends a subscription. Use this to resume a paused subscription."""
    sub = get_or_404(db, Subscription, sub_id, "Subscription")
    if sub.status == SubStatus.closed:
        raise DomainError("Closed subscriptions cannot be extended")
    if body.expiry_date <= sub.start_date:
        raise DomainError("Expiry date must be after the start date")
    sub.expiry_date = body.expiry_date
    db.commit()
    return sub_out(sub, detail=True)
