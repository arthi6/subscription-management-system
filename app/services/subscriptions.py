from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import DomainError
from app.models import (Discount, Plan, ProductVariant, QuotationTemplate, Role, Subscription,
                        SubscriptionLine, SubscriptionStatusLog, SubStatus, User)
from app.services.common import D, money, sum_money

# The subscription state machine. Anything not listed here is rejected.
ALLOWED_TRANSITIONS = {
    SubStatus.draft: {SubStatus.quotation, SubStatus.closed},
    SubStatus.quotation: {SubStatus.confirmed, SubStatus.closed},
    SubStatus.confirmed: {SubStatus.active, SubStatus.closed},
    SubStatus.active: {SubStatus.closed},
    SubStatus.closed: set(),
}


def transition(db: Session, sub: Subscription, to_status: SubStatus, actor_id: int | None = None) -> None:
    if to_status not in ALLOWED_TRANSITIONS[sub.status]:
        raise DomainError(f"Cannot move a subscription from {sub.status.value} to {to_status.value}")
    if to_status == SubStatus.confirmed and sub.quotation_valid_until and sub.quotation_valid_until < date.today():
        raise DomainError("The quotation has expired and must be recreated from its template")
    db.add(SubscriptionStatusLog(subscription=sub, from_status=sub.status,
                                 to_status=to_status, changed_by_id=actor_id))
    sub.status = to_status


def activate_subscription(db: Session, sub: Subscription, actor_id: int | None = None) -> None:
    """Convenience for draft subscriptions: draft -> quotation -> confirmed -> active."""
    for target in (SubStatus.quotation, SubStatus.confirmed, SubStatus.active):
        transition(db, sub, target, actor_id)
    db.commit()


def create_subscription(
    db: Session,
    *,
    customer: User,
    plan: Plan,
    quantity: int,
    start_date: date,
    expiry_date: date,
    variant_ids: list[int] | None = None,
    discount: Discount | None = None,
    template: QuotationTemplate | None = None,
    payment_terms_days: int | None = None,
    actor_id: int | None = None,
) -> Subscription:
    variant_ids = variant_ids or []
    if customer.role != Role.customer:
        raise DomainError("Subscriptions can only belong to customer accounts")
    if not plan.is_active:
        raise DomainError("This plan is closed for new subscriptions")
    if quantity < plan.min_quantity:
        raise DomainError(f"Minimum quantity for this plan is {plan.min_quantity}")
    if start_date < plan.available_from or (plan.available_to and start_date > plan.available_to):
        raise DomainError("The plan is not available on the requested start date")
    if expiry_date <= start_date:
        raise DomainError("Expiry date must be after the start date")
    if discount is not None and not discount.is_active:
        raise DomainError("This discount is not active")

    variants = []
    if variant_ids:
        variants = list(db.scalars(select(ProductVariant).where(ProductVariant.id.in_(variant_ids))))
        if len(variants) != len(set(variant_ids)) or any(v.product_id != plan.product_id for v in variants):
            raise DomainError("Every variant must belong to the plan's product")

    unit_price = money(sum_money([plan.price] + [v.price_extra for v in variants]))
    description = plan.name
    if variants:
        description += " (" + ", ".join(f"{v.attribute}: {v.value}" for v in variants) + ")"

    if template is not None:
        status = SubStatus.quotation
        valid_until = date.today() + timedelta(days=template.validity_days)
    else:
        status = SubStatus.draft
        valid_until = None

    sub = Subscription(
        number=f"TMP-{uuid4().hex}",  # replaced with the sequential number after the first flush
        customer=customer, plan=plan, discount=discount, template=template,
        status=status, quantity=quantity, start_date=start_date, expiry_date=expiry_date,
        next_billing_date=start_date,
        payment_terms_days=payment_terms_days if payment_terms_days is not None
        else settings.default_payment_terms_days,
        quotation_valid_until=valid_until,
    )
    sub.lines.append(SubscriptionLine(
        product=plan.product, description=description, quantity=quantity,
        unit_price=unit_price, tax=plan.product.tax,
    ))
    db.add(sub)
    db.flush()
    sub.number = f"SUB-{sub.id:06d}"
    db.add(SubscriptionStatusLog(subscription=sub, from_status=None, to_status=status, changed_by_id=actor_id))
    db.commit()
    return sub
