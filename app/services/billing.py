import json
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.database import utcnow
from app.errors import DomainError
from app.models import (BillingRun, Discount, DiscountKind, DiscountScope, EndBehavior, Invoice,
                        InvoiceLine, InvoiceStatus, Subscription, SubStatus)
from app.services.common import D, add_period, money, sum_money
from app.services.subscriptions import transition


# ---------- discounts -------------------------------------------------------------

def _line_specs(sub: Subscription) -> list[dict]:
    specs = []
    for sl in sub.lines:
        subtotal = money(D(sl.unit_price) * sl.quantity)
        rate = D(sl.tax.rate) if sl.tax is not None else Decimal("0")
        specs.append({"line": sl, "subtotal": subtotal, "discount": Decimal("0"), "rate": rate})
    return specs


def _find_discount(sub: Subscription, specs: list[dict], period_start):
    """Returns (discount, target_specs, base, amount) when a discount applies to this period, else None."""
    d = sub.discount
    if d is None or not d.is_active:
        return None
    if period_start < d.start_date or (d.end_date and period_start > d.end_date):
        return None
    targets = [s for s in specs
               if d.scope == DiscountScope.subscription or s["line"].product_id == d.product_id]
    if not targets:
        return None
    base = sum_money(s["subtotal"] for s in targets)
    qty = sum(s["line"].quantity for s in targets)
    if base <= 0 or base < D(d.min_purchase) or qty < d.min_quantity:
        return None
    if d.kind == DiscountKind.fixed:
        amount = min(D(d.value), base)
    else:
        amount = money(base * D(d.value) / 100)
    return d, targets, base, amount


def _consume_usage(db: Session, discount_id: int) -> bool:
    """Atomic check-and-increment. Two concurrent billing runs cannot exceed usage_limit."""
    result = db.execute(
        update(Discount)
        .where(Discount.id == discount_id,
               or_(Discount.usage_limit.is_(None), Discount.used_count < Discount.usage_limit))
        .values(used_count=Discount.used_count + 1)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


# ---------- invoice construction ----------------------------------------------------

def build_invoice(db: Session, sub: Subscription, period_start, period_end) -> Invoice:
    specs = _line_specs(sub)

    discount_id = None
    found = _find_discount(sub, specs, period_start)
    if found is not None:
        d, targets, base, amount = found
        if _consume_usage(db, d.id):
            discount_id = d.id
            remaining = amount
            for i, s in enumerate(targets):
                if i == len(targets) - 1:
                    share = remaining  # last line absorbs rounding so shares sum exactly to amount
                else:
                    share = money(amount * s["subtotal"] / base)
                    remaining -= share
                s["discount"] = share

    invoice = Invoice(
        subscription_id=sub.id, customer_id=sub.customer_id, status=InvoiceStatus.draft,
        period_start=period_start, period_end=period_end, invoice_date=period_start,
        due_date=period_start + timedelta(days=sub.payment_terms_days), discount_id=discount_id,
    )
    for s in specs:
        sl = s["line"]
        taxable = s["subtotal"] - s["discount"]
        tax = money(taxable * s["rate"] / 100)
        invoice.lines.append(InvoiceLine(
            product_id=sl.product_id, description=sl.description, quantity=sl.quantity,
            unit_price=money(sl.unit_price), subtotal=s["subtotal"], discount_amount=s["discount"],
            tax_rate=s["rate"], tax_amount=tax, line_total=taxable + tax,
        ))
    invoice.subtotal = sum_money(s["subtotal"] for s in specs)
    invoice.discount_total = sum_money(s["discount"] for s in specs)
    invoice.tax_total = sum_money(l.tax_amount for l in invoice.lines)
    invoice.total = sum_money(l.line_total for l in invoice.lines)
    invoice.amount_paid = Decimal("0.00")
    db.add(invoice)
    return invoice


# ---------- billing run -----------------------------------------------------------

def bill_subscription(db: Session, sub: Subscription, run_date, actor_id: int | None = None) -> list[Invoice]:
    """Creates one invoice for every billing period that has come due, up to run_date.
    Catches up missed periods, and never creates a second invoice for the same period."""
    plan = sub.plan
    created: list[Invoice] = []
    for _ in range(400):  # guard against runaway catch-up loops
        if sub.status != SubStatus.active or sub.next_billing_date > run_date:
            break
        period_start = sub.next_billing_date

        if plan.end_behavior == EndBehavior.renew:
            while sub.expiry_date <= period_start:
                sub.expiry_date = add_period(sub.expiry_date, plan.billing_period)
        elif period_start >= sub.expiry_date:
            if plan.end_behavior == EndBehavior.auto_close:
                transition(db, sub, SubStatus.closed, actor_id)
            break  # pause and manual_close stop billing here until an admin acts

        period_end = add_period(period_start, plan.billing_period) - timedelta(days=1)
        already = db.scalar(select(Invoice.id).where(
            Invoice.subscription_id == sub.id, Invoice.period_start == period_start))
        if already is None:
            created.append(build_invoice(db, sub, period_start, period_end))
            db.flush()
        sub.next_billing_date = add_period(period_start, plan.billing_period)
    else:
        raise DomainError("Billing loop limit reached; check the subscription's dates")
    return created


def run_billing(db: Session, run_date, actor_id: int | None = None) -> BillingRun:
    run = BillingRun(run_date=run_date, started_at=utcnow(), triggered_by_id=actor_id,
                     invoices_created=0, subscriptions_skipped=0)
    db.add(run)
    db.flush()

    due = db.scalars(
        select(Subscription)
        .where(Subscription.status == SubStatus.active, Subscription.next_billing_date <= run_date)
        .order_by(Subscription.id)
    ).all()

    errors = []
    for sub in due:
        number = sub.number
        try:
            # Savepoint per subscription: one failure is logged and does not stop the run.
            with db.begin_nested():
                created = bill_subscription(db, sub, run_date, actor_id)
            run.invoices_created += len(created)
            if not created:
                run.subscriptions_skipped += 1
        except Exception as exc:  # noqa: BLE001 - we record every failure, never swallow silently
            errors.append({"subscription": number, "error": str(exc)})
            run.subscriptions_skipped += 1

    run.errors = json.dumps(errors) if errors else None
    run.finished_at = utcnow()
    db.commit()
    return run


# ---------- invoice actions ------------------------------------------------------------

def confirm_invoice(db: Session, invoice: Invoice) -> None:
    if invoice.status != InvoiceStatus.draft:
        raise DomainError("Only draft invoices can be confirmed")
    invoice.status = InvoiceStatus.confirmed
    db.flush()
    invoice.number = f"INV-{invoice.invoice_date.year}-{invoice.id:06d}"
    db.commit()


def cancel_invoice(db: Session, invoice: Invoice) -> None:
    if invoice.status not in (InvoiceStatus.draft, InvoiceStatus.confirmed):
        raise DomainError("Only draft or confirmed invoices can be cancelled")
    if invoice.amount_paid > 0:
        raise DomainError("Invoices with payments cannot be cancelled")
    if invoice.discount_id:
        # Give the discount use back, since this invoice will not be paid.
        db.execute(update(Discount)
                   .where(Discount.id == invoice.discount_id, Discount.used_count > 0)
                   .values(used_count=Discount.used_count - 1)
                   .execution_options(synchronize_session=False))
    invoice.status = InvoiceStatus.cancelled
    db.commit()
