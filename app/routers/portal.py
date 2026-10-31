from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Invoice, InvoiceStatus, Role, Subscription, User
from app.serializers import invoice_out, sub_out
from app.services.common import paginate

router = APIRouter(prefix="/portal", tags=["customer portal"])
customer_only = require_roles(Role.customer)


@router.get("/subscriptions")
def my_subscriptions(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                     user: User = Depends(customer_only), db: Session = Depends(get_db)):
    stmt = select(Subscription).where(Subscription.customer_id == user.id).order_by(Subscription.id.desc())
    result = paginate(db, stmt, page, page_size)
    result["items"] = [sub_out(s) for s in result["items"]]
    return result


@router.get("/subscriptions/{sub_id}")
def my_subscription(sub_id: int, user: User = Depends(customer_only), db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscription).where(Subscription.id == sub_id, Subscription.customer_id == user.id))
    if sub is None:  # same 404 whether it does not exist or belongs to someone else
        raise HTTPException(404, "Subscription not found")
    return sub_out(sub, detail=True)


@router.get("/invoices")
def my_invoices(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                user: User = Depends(customer_only), db: Session = Depends(get_db)):
    stmt = (select(Invoice)
            .where(Invoice.customer_id == user.id, Invoice.status != InvoiceStatus.draft)
            .order_by(Invoice.id.desc()))
    result = paginate(db, stmt, page, page_size)
    result["items"] = [invoice_out(i) for i in result["items"]]
    return result


@router.get("/invoices/{invoice_id}")
def my_invoice(invoice_id: int, user: User = Depends(customer_only), db: Session = Depends(get_db)):
    inv = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.customer_id == user.id,
                                          Invoice.status != InvoiceStatus.draft))
    if inv is None:
        raise HTTPException(404, "Invoice not found")
    return invoice_out(inv, detail=True)
