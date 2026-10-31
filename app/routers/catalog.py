from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_or_404, require_roles
from app.errors import DomainError
from app.models import Discount, DiscountScope, Plan, Product, ProductVariant, QuotationTemplate, Role, Tax
from app.schemas import DiscountIn, PlanIn, ProductIn, ProductUpdate, TaxIn, TemplateIn, VariantIn
from app.serializers import discount_out, plan_out, product_out, tax_out, template_out

router = APIRouter(prefix="/catalog", tags=["catalog"])
admin_only = require_roles(Role.admin)
read_access = require_roles(Role.admin, Role.staff)


@router.post("/taxes", status_code=201)
def create_tax(body: TaxIn, _=Depends(admin_only), db: Session = Depends(get_db)):
    tax = Tax(name=body.name, rate=body.rate)
    db.add(tax)
    db.commit()
    return tax_out(tax)


@router.get("/taxes")
def list_taxes(_=Depends(read_access), db: Session = Depends(get_db)):
    return [tax_out(t) for t in db.scalars(select(Tax).order_by(Tax.id))]


@router.post("/products", status_code=201)
def create_product(body: ProductIn, _=Depends(admin_only), db: Session = Depends(get_db)):
    if body.tax_id is not None:
        get_or_404(db, Tax, body.tax_id, "Tax")
    product = Product(**body.model_dump())
    db.add(product)
    db.commit()
    return product_out(product)


@router.patch("/products/{product_id}")
def update_product(product_id: int, body: ProductUpdate, _=Depends(admin_only), db: Session = Depends(get_db)):
    product = get_or_404(db, Product, product_id, "Product")
    changes = body.model_dump(exclude_unset=True)
    for field in ("name", "product_type", "sales_price", "cost_price"):
        if field in changes and changes[field] is None:
            raise DomainError(f"{field} cannot be empty")
    if changes.get("tax_id") is not None:
        get_or_404(db, Tax, changes["tax_id"], "Tax")
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product_out(product)


@router.get("/products")
def list_products(_=Depends(read_access), db: Session = Depends(get_db)):
    return [product_out(p) for p in db.scalars(select(Product).order_by(Product.id))]


@router.post("/products/{product_id}/variants", status_code=201)
def add_variant(product_id: int, body: VariantIn, _=Depends(admin_only), db: Session = Depends(get_db)):
    product = get_or_404(db, Product, product_id, "Product")
    variant = ProductVariant(product_id=product.id, **body.model_dump())
    db.add(variant)
    db.commit()
    db.refresh(product)
    return product_out(product)


@router.post("/plans", status_code=201)
def create_plan(body: PlanIn, _=Depends(admin_only), db: Session = Depends(get_db)):
    get_or_404(db, Product, body.product_id, "Product")
    if body.available_to and body.available_to < body.available_from:
        raise DomainError("available_to cannot be before available_from")
    plan = Plan(**body.model_dump())
    db.add(plan)
    db.commit()
    return plan_out(plan)


@router.get("/plans")
def list_plans(active_only: bool = Query(True), _=Depends(read_access), db: Session = Depends(get_db)):
    stmt = select(Plan).order_by(Plan.id)
    if active_only:
        stmt = stmt.where(Plan.is_active.is_(True))
    return [plan_out(p) for p in db.scalars(stmt)]


@router.post("/plans/{plan_id}/close")
def close_plan(plan_id: int, _=Depends(admin_only), db: Session = Depends(get_db)):
    """Stops new subscriptions on this plan. Existing subscriptions are not affected."""
    plan = get_or_404(db, Plan, plan_id, "Plan")
    plan.is_active = False
    db.commit()
    return plan_out(plan)


@router.post("/quotation-templates", status_code=201)
def create_template(body: TemplateIn, _=Depends(admin_only), db: Session = Depends(get_db)):
    get_or_404(db, Plan, body.plan_id, "Plan")
    template = QuotationTemplate(**body.model_dump())
    db.add(template)
    db.commit()
    return template_out(template)


@router.get("/quotation-templates")
def list_templates(_=Depends(read_access), db: Session = Depends(get_db)):
    return [template_out(t) for t in db.scalars(select(QuotationTemplate).order_by(QuotationTemplate.id))]


@router.post("/discounts", status_code=201)
def create_discount(body: DiscountIn, _=Depends(admin_only), db: Session = Depends(get_db)):
    if body.product_id is not None:
        get_or_404(db, Product, body.product_id, "Product")
    discount = Discount(**body.model_dump())
    db.add(discount)
    db.commit()
    return discount_out(discount)


@router.get("/discounts")
def list_discounts(_=Depends(read_access), db: Session = Depends(get_db)):
    return [discount_out(d) for d in db.scalars(select(Discount).order_by(Discount.id))]


@router.post("/discounts/{discount_id}/deactivate")
def deactivate_discount(discount_id: int, _=Depends(admin_only), db: Session = Depends(get_db)):
    discount = get_or_404(db, Discount, discount_id, "Discount")
    discount.is_active = False
    db.commit()
    return discount_out(discount)
