from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import DomainError
from app.models import Invoice, InvoiceStatus, Payment, PaymentMethod
from app.services.common import D, money


def record_payment(db: Session, invoice: Invoice, method: PaymentMethod, amount, paid_on: date,
                   note: str | None, actor_id: int | None) -> Payment:
    if invoice.status != InvoiceStatus.confirmed:
        raise DomainError("Payments can only be recorded against confirmed invoices")
    amount = money(amount)
    balance = D(invoice.total) - D(invoice.amount_paid)
    if amount > balance:
        raise DomainError(f"Payment of {amount} exceeds the outstanding balance of {money(balance)}")

    payment = Payment(invoice_id=invoice.id, method=method, amount=amount, paid_on=paid_on,
                      note=note, recorded_by_id=actor_id)
    db.add(payment)
    db.flush()
    # Derive paid amount from the payments table, so the invoice never drifts from its payments.
    invoice.amount_paid = money(db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice.id)))
    if invoice.amount_paid >= invoice.total:
        invoice.status = InvoiceStatus.paid
    db.commit()
    return payment
