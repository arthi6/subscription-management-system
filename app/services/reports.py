from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select, true
from sqlalchemy.orm import Session

from app.models import (BillingPeriod, Invoice, InvoiceStatus, Payment, Plan, Subscription,
                        SubscriptionLine, SubStatus)
from app.services.common import D, money, sum_money

MONTHLY_FACTOR = {
    BillingPeriod.daily: Decimal(365) / Decimal(12),
    BillingPeriod.weekly: Decimal(52) / Decimal(12),
    BillingPeriod.monthly: Decimal(1),
    BillingPeriod.yearly: Decimal(1) / Decimal(12),
}


def overdue_conditions(today: date) -> list:
    return [Invoice.status == InvoiceStatus.confirmed,
            Invoice.due_date < today,
            Invoice.total > Invoice.amount_paid]


def summary(db: Session, start: date, end: date, plan_id: int | None = None,
            customer_id: int | None = None) -> dict:
    today = date.today()
    sub_filters = [true()]
    if plan_id:
        sub_filters.append(Subscription.plan_id == plan_id)
    if customer_id:
        sub_filters.append(Subscription.customer_id == customer_id)

    sub_ids = select(Subscription.id).where(*sub_filters)
    inv_scope = Invoice.subscription_id.in_(sub_ids)
    pay_scope = Payment.invoice_id.in_(select(Invoice.id).where(inv_scope))

    active_count = db.scalar(select(func.count(Subscription.id)).where(
        Subscription.status == SubStatus.active, *sub_filters)) or 0

    # Recurring value grouped by billing period, normalised to a monthly figure.
    rows = db.execute(
        select(Plan.billing_period, func.sum(SubscriptionLine.unit_price * SubscriptionLine.quantity))
        .select_from(SubscriptionLine)
        .join(Subscription, Subscription.id == SubscriptionLine.subscription_id)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.status == SubStatus.active, *sub_filters)
        .group_by(Plan.billing_period)
    ).all()
    mrr = sum_money(MONTHLY_FACTOR[period] * D(value or 0) for period, value in rows)

    invoiced = db.scalar(select(func.sum(Invoice.total)).where(
        Invoice.invoice_date >= start, Invoice.invoice_date <= end,
        Invoice.status != InvoiceStatus.cancelled, inv_scope)) or 0

    collected = db.scalar(select(func.sum(Payment.amount)).where(
        Payment.paid_on >= start, Payment.paid_on <= end, pay_scope)) or 0

    outstanding = db.scalar(select(func.sum(Invoice.total - Invoice.amount_paid)).where(
        Invoice.status == InvoiceStatus.confirmed, inv_scope)) or 0

    overdue_where = and_(*overdue_conditions(today), inv_scope)
    overdue_count = db.scalar(select(func.count(Invoice.id)).where(overdue_where)) or 0
    overdue_amount = db.scalar(select(func.sum(Invoice.total - Invoice.amount_paid)).where(overdue_where)) or 0

    def bucket(min_days: int, max_days: int | None):
        # days overdue = today - due_date; a bucket is [min_days, max_days] days overdue
        where = [*overdue_conditions(today), inv_scope, Invoice.due_date <= today - timedelta(days=min_days)]
        if max_days is not None:
            where.append(Invoice.due_date >= today - timedelta(days=max_days))
        count = db.scalar(select(func.count(Invoice.id)).where(and_(*where))) or 0
        amount = db.scalar(select(func.sum(Invoice.total - Invoice.amount_paid)).where(and_(*where))) or 0
        return {"count": count, "amount": money(amount)}

    return {
        "period": {"start": start, "end": end},
        "active_subscriptions": active_count,
        "monthly_recurring_revenue": money(mrr),
        "invoiced_in_period": money(invoiced),
        "collected_in_period": money(collected),
        "outstanding_balance": money(outstanding),
        "overdue": {"count": overdue_count, "amount": money(overdue_amount)},
        "aging": {"1-30_days": bucket(1, 30), "31-60_days": bucket(31, 60), "61_plus_days": bucket(61, None)},
    }
