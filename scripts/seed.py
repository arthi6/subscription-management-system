"""Loads demo data for performance checks.

    python -m scripts.seed --customers 5000

Creates one product, tax and plan, then one active subscription per customer.
All seed customers share one password hash (Seed@Pass1) to keep seeding fast.
"""
import argparse
from datetime import date
from decimal import Decimal

from app.database import Base, SessionLocal, engine
from app.models import BillingPeriod, EndBehavior, Plan, Product, Role, Tax, User
from app.security import hash_password
from app.services.subscriptions import activate_subscription, create_subscription


def main(n_customers: int) -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        tax = Tax(name="GST 18% (seed)", rate=Decimal("18"))
        product = Product(name="Odoo Suite (seed)", product_type="software",
                          sales_price=Decimal("999"), cost_price=Decimal("400"), tax=tax)
        db.add(product)
        db.flush()
        plan = Plan(name="Monthly Standard (seed)", product_id=product.id, price=Decimal("999"),
                    billing_period=BillingPeriod.monthly, min_quantity=1,
                    available_from=date(2025, 1, 1), end_behavior=EndBehavior.renew)
        db.add(plan)
        db.commit()

        shared_hash = hash_password("Seed@Pass1")
        for i in range(n_customers):
            customer = User(email=f"seed{i}@example.com", full_name=f"Seed Customer {i}",
                            password_hash=shared_hash, role=Role.customer)
            db.add(customer)
            db.commit()
            sub = create_subscription(db, customer=customer, plan=plan, quantity=1 + i % 5,
                                      start_date=date(2025, 1, 1), expiry_date=date(2028, 12, 31))
            activate_subscription(db, sub)
            if (i + 1) % 500 == 0:
                print(f"seeded {i + 1} subscriptions")
    print(f"Done. {n_customers} active subscriptions created.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--customers", type=int, default=2000)
    main(parser.parse_args().customers)
