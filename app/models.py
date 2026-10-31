from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index,
                        Integer, Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow


class Role(str, enum.Enum):
    admin = "admin"
    staff = "staff"
    customer = "customer"


class BillingPeriod(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class EndBehavior(str, enum.Enum):
    auto_close = "auto_close"      # close the subscription when it expires
    manual_close = "manual_close"  # stop billing at expiry; an admin closes it
    pause = "pause"                # stop billing at expiry; an admin extends expiry to resume
    renew = "renew"                # extend expiry by one billing period and keep billing


class SubStatus(str, enum.Enum):
    draft = "draft"
    quotation = "quotation"
    confirmed = "confirmed"
    active = "active"
    closed = "closed"


class DiscountKind(str, enum.Enum):
    fixed = "fixed"
    percent = "percent"


class DiscountScope(str, enum.Enum):
    product = "product"
    subscription = "subscription"


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    paid = "paid"
    cancelled = "cancelled"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    bank_transfer = "bank_transfer"
    card = "card"
    upi = "upi"
    cheque = "cheque"


def _enum(cls):
    return Enum(cls, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.customer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PasswordResetToken(Base):
    """Only a SHA-256 hash of the reset token is stored, never the token itself."""
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Tax(Base):
    __tablename__ = "taxes"
    __table_args__ = (CheckConstraint("rate >= 0 AND rate <= 100", name="ck_tax_rate_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    product_type: Mapped[str] = mapped_column(String(50), default="service")
    sales_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tax_id: Mapped[Optional[int]] = mapped_column(ForeignKey("taxes.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tax: Mapped[Optional[Tax]] = relationship()
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductVariant.id")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("product_id", "attribute", "value", name="uq_variant_value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    attribute: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(100))
    price_extra: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    product: Mapped[Product] = relationship(back_populates="variants")


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_plan_price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    billing_period: Mapped[BillingPeriod] = mapped_column(_enum(BillingPeriod))
    min_quantity: Mapped[int] = mapped_column(Integer, default=1)
    available_from: Mapped[date] = mapped_column(Date)
    available_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_behavior: Mapped[EndBehavior] = mapped_column(_enum(EndBehavior), default=EndBehavior.manual_close)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped[Product] = relationship()


class QuotationTemplate(Base):
    __tablename__ = "quotation_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    validity_days: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    plan: Mapped[Plan] = relationship()


class Discount(Base):
    __tablename__ = "discounts"
    __table_args__ = (
        CheckConstraint("value > 0", name="ck_discount_value_positive"),
        CheckConstraint("used_count >= 0", name="ck_discount_used_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[DiscountKind] = mapped_column(_enum(DiscountKind))
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    scope: Mapped[DiscountScope] = mapped_column(_enum(DiscountScope))
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    min_purchase: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    min_quantity: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (Index("ix_subscriptions_status_next_billing", "status", "next_billing_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("quotation_templates.id"), nullable=True)
    discount_id: Mapped[Optional[int]] = mapped_column(ForeignKey("discounts.id"), nullable=True)
    status: Mapped[SubStatus] = mapped_column(_enum(SubStatus), default=SubStatus.draft)
    quantity: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date] = mapped_column(Date)
    next_billing_date: Mapped[date] = mapped_column(Date)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=14)
    quotation_valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    customer: Mapped[User] = relationship()
    plan: Mapped[Plan] = relationship()
    discount: Mapped[Optional[Discount]] = relationship()
    template: Mapped[Optional[QuotationTemplate]] = relationship()
    lines: Mapped[list["SubscriptionLine"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan", order_by="SubscriptionLine.id")
    status_logs: Mapped[list["SubscriptionStatusLog"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan", order_by="SubscriptionStatusLog.id")


class SubscriptionLine(Base):
    __tablename__ = "subscription_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_sub_line_qty_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    description: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax_id: Mapped[Optional[int]] = mapped_column(ForeignKey("taxes.id"), nullable=True)

    subscription: Mapped[Subscription] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()
    tax: Mapped[Optional[Tax]] = relationship()


class SubscriptionStatusLog(Base):
    __tablename__ = "subscription_status_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[Optional[SubStatus]] = mapped_column(_enum(SubStatus), nullable=True)
    to_status: Mapped[SubStatus] = mapped_column(_enum(SubStatus))
    changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    subscription: Mapped[Subscription] = relationship(back_populates="status_logs")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        # Core billing guarantee: one invoice per subscription per billing period, enforced by the DB.
        UniqueConstraint("subscription_id", "period_start", name="uq_invoice_subscription_period"),
        Index("ix_invoices_status_due", "status", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    discount_id: Mapped[Optional[int]] = mapped_column(ForeignKey("discounts.id"), nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(_enum(InvoiceStatus), default=InvoiceStatus.draft)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    customer: Mapped[User] = relationship()
    subscription: Mapped[Subscription] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLine.id")
    payments: Mapped[list["Payment"]] = relationship(order_by="Payment.id")


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    invoice: Mapped[Invoice] = relationship(back_populates="lines")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(_enum(PaymentMethod))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_on: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    recorded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BillingRun(Base):
    __tablename__ = "billing_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_date: Mapped[date] = mapped_column(Date)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    invoices_created: Mapped[int] = mapped_column(Integer, default=0)
    subscriptions_skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of per-subscription failures
    triggered_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
