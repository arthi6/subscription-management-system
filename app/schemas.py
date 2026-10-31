import re
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models import (BillingPeriod, DiscountKind, DiscountScope, EndBehavior,
                        PaymentMethod, Role, SubStatus)


def check_password(password: str) -> str:
    """Brief rules: more than 8 characters, one uppercase, one lowercase, one special character."""
    problems = []
    if len(password) <= 8:
        problems.append("be more than 8 characters long")
    if not re.search(r"[A-Z]", password):
        problems.append("contain an uppercase letter")
    if not re.search(r"[a-z]", password):
        problems.append("contain a lowercase letter")
    if not re.search(r"[^A-Za-z0-9]", password):
        problems.append("contain a special character")
    if len(password.encode("utf-8")) > 72:
        problems.append("be at most 72 bytes long")
    if problems:
        raise ValueError("Password must " + ", ".join(problems))
    return password


class SignupIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str

    @field_validator("password")
    @classmethod
    def _password_rules(cls, v: str) -> str:
        return check_password(v)


class StaffIn(SignupIn):
    role: Role = Role.staff

    @field_validator("role")
    @classmethod
    def _not_customer(cls, v: Role) -> Role:
        if v == Role.customer:
            raise ValueError("Staff accounts must use the staff or admin role")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password_rules(cls, v: str) -> str:
        return check_password(v)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TaxIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    rate: Decimal = Field(ge=0, le=100)


class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    product_type: str = Field(default="service", max_length=50)
    sales_price: Decimal = Field(ge=0)
    cost_price: Decimal = Field(default=Decimal("0"), ge=0)
    notes: Optional[str] = None
    tax_id: Optional[int] = None


class VariantIn(BaseModel):
    attribute: str = Field(min_length=1, max_length=50)
    value: str = Field(min_length=1, max_length=100)
    price_extra: Decimal = Field(default=Decimal("0"))


class PlanIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    product_id: int
    price: Decimal = Field(ge=0)
    billing_period: BillingPeriod
    min_quantity: int = Field(default=1, ge=1)
    available_from: date
    available_to: Optional[date] = None
    end_behavior: EndBehavior = EndBehavior.manual_close


class TemplateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    plan_id: int
    validity_days: int = Field(ge=1, le=365)


class DiscountIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kind: DiscountKind
    value: Decimal = Field(gt=0)
    scope: DiscountScope
    product_id: Optional[int] = None
    min_purchase: Decimal = Field(default=Decimal("0"), ge=0)
    min_quantity: int = Field(default=0, ge=0)
    start_date: date
    end_date: Optional[date] = None
    usage_limit: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _check_rules(self):
        if self.scope == DiscountScope.product and self.product_id is None:
            raise ValueError("Product-scoped discounts need a product_id")
        if self.scope == DiscountScope.subscription and self.product_id is not None:
            raise ValueError("Subscription-scoped discounts must not set product_id")
        if self.kind == DiscountKind.percent and self.value > 100:
            raise ValueError("A percentage discount cannot exceed 100")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class SubscriptionIn(BaseModel):
    customer_id: int
    plan_id: int
    quantity: int = Field(ge=1)
    start_date: date
    expiry_date: date
    variant_ids: list[int] = Field(default_factory=list)
    discount_id: Optional[int] = None
    payment_terms_days: Optional[int] = Field(default=None, ge=0, le=365)


class FromTemplateIn(BaseModel):
    customer_id: int
    quantity: int = Field(ge=1)
    start_date: date
    expiry_date: date
    variant_ids: list[int] = Field(default_factory=list)
    discount_id: Optional[int] = None


class TransitionIn(BaseModel):
    status: SubStatus


class ExpiryIn(BaseModel):
    expiry_date: date


class PaymentIn(BaseModel):
    method: PaymentMethod
    amount: Decimal = Field(gt=0)
    paid_on: date
    note: Optional[str] = Field(default=None, max_length=500)
