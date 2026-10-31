from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.database import get_db, utcnow
from app.deps import get_current_user, get_or_404, require_roles
from app.errors import DomainError
from app.mailer import send_email
from app.models import Invoice, InvoiceStatus, PaymentMethod, Role, User
from app.schemas import PaymentIn
from app.serializers import invoice_out, payment_out, run_out
from app.services.billing import cancel_invoice, confirm_invoice, run_billing
from app.services.common import money, paginate
from app.services.invoice_document import render_invoice_html
from app.services.payments import record_payment
from app.services.reports import overdue_conditions

router = APIRouter(tags=["billing and invoices"])
ops = require_roles(Role.admin, Role.staff)


# ---- billing runs -----------------------------------------------------------------

@router.post("/billing/runs", status_code=201)
def trigger_billing_run(run_date: Optional[date] = Query(None), user: User = Depends(ops),
                        db: Session = Depends(get_db)):
    """Bills every active subscription that is due on or before run_date (default: today).
    Safe to run repeatedly: already-billed periods are skipped, never duplicated."""
    return run_out(run_billing(db, run_date or date.today(), actor_id=user.id))


@router.get("/billing/runs")
def list_billing_runs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                      _user: User = Depends(ops), db: Session = Depends(get_db)):
    from app.models import BillingRun
    stmt = select(BillingRun).order_by(BillingRun.id.desc())
    result = paginate(db, stmt, page, page_size)
    result["items"] = [run_out(r) for r in result["items"]]
    return result


# ---- invoices -----------------------------------------------------------------------

@router.get("/invoices")
def list_invoices(
    status_filter: Optional[InvoiceStatus] = Query(None, alias="status"),
    customer_id: Optional[int] = None,
    overdue: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: User = Depends(ops),
    db: Session = Depends(get_db),
):
    stmt = select(Invoice).order_by(Invoice.id.desc())
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if overdue:
        stmt = stmt.where(and_(*overdue_conditions(date.today())))
    result = paginate(db, stmt, page, page_size)
    result["items"] = [invoice_out(i) for i in result["items"]]
    return result


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, _user: User = Depends(ops), db: Session = Depends(get_db)):
    return invoice_out(get_or_404(db, Invoice, invoice_id, "Invoice"), detail=True)


@router.post("/invoices/{invoice_id}/confirm")
def confirm(invoice_id: int, _user: User = Depends(ops), db: Session = Depends(get_db)):
    invoice = get_or_404(db, Invoice, invoice_id, "Invoice")
    confirm_invoice(db, invoice)
    return invoice_out(invoice, detail=True)


@router.post("/invoices/{invoice_id}/cancel")
def cancel(invoice_id: int, _user: User = Depends(ops), db: Session = Depends(get_db)):
    invoice = get_or_404(db, Invoice, invoice_id, "Invoice")
    cancel_invoice(db, invoice)
    return invoice_out(invoice, detail=True)


@router.post("/invoices/{invoice_id}/send")
def send(invoice_id: int, _user: User = Depends(ops), db: Session = Depends(get_db)):
    invoice = get_or_404(db, Invoice, invoice_id, "Invoice")
    if invoice.status == InvoiceStatus.draft:
        raise DomainError("Confirm the invoice before sending it")
    send_email(invoice.customer.email, f"Invoice {invoice.number}",
               f"Invoice {invoice.number} for {invoice.total} is due on {invoice.due_date}.\n"
               f"Outstanding balance: {invoice.total - invoice.amount_paid}.")
    invoice.sent_at = utcnow()
    db.commit()
    return invoice_out(invoice)


@router.get("/invoices/{invoice_id}/print", response_class=HTMLResponse)
def print_invoice(invoice_id: int, _user: User = Depends(ops), db: Session = Depends(get_db)):
    """Print-ready A4 HTML invoice. Admin and staff only; unknown ids return 404."""
    inv = get_or_404(db, Invoice, invoice_id, "Invoice")
    return HTMLResponse(
        render_invoice_html(inv),
        headers={
            "Content-Disposition": 'inline; filename="invoice-' + str(inv.number or f"draft-{inv.id}") + '.html"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            # The document needs no scripts or remote assets; forbid them as defence in depth.
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )


@router.post("/invoices/reminders")
def send_overdue_reminders(_user: User = Depends(ops), db: Session = Depends(get_db)):
    overdue = db.scalars(select(Invoice).where(and_(*overdue_conditions(date.today())))).all()
    for inv in overdue:
        send_email(inv.customer.email, f"Payment reminder: {inv.number}",
                   f"Balance of {inv.total - inv.amount_paid} was due on {inv.due_date}.")
    return {"reminders_sent": len(overdue)}


# ---- payments -------------------------------------------------------------------------

@router.post("/invoices/{invoice_id}/payments", status_code=201)
def add_payment(invoice_id: int, body: PaymentIn, user: User = Depends(ops), db: Session = Depends(get_db)):
    # Row lock so two simultaneous payments cannot both pass the balance check (Postgres).
    invoice = db.get(Invoice, invoice_id, with_for_update=True)
    if invoice is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Invoice not found")
    payment = record_payment(db, invoice, body.method, body.amount, body.paid_on, body.note, user.id)
    return payment_out(payment)


@router.get("/invoices/{invoice_id}/payments")
def list_payments(invoice_id: int, _user: User = Depends(ops), db: Session = Depends(get_db)):
    inv = get_or_404(db, Invoice, invoice_id, "Invoice")
    return [payment_out(p) for p in inv.payments]
