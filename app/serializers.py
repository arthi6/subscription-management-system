from app.config import settings
import json


def user_out(u):
    return {"id": u.id, "email": u.email, "full_name": u.full_name,
            "role": u.role.value, "is_active": u.is_active}


def tax_out(t):
    return {"id": t.id, "name": t.name, "rate": t.rate, "is_active": t.is_active}


def product_out(p):
    return {
        "id": p.id, "name": p.name, "product_type": p.product_type,
        "sales_price": p.sales_price, "cost_price": p.cost_price, "notes": p.notes,
        "tax_id": p.tax_id, "is_active": p.is_active,
        "variants": [{"id": v.id, "attribute": v.attribute, "value": v.value,
                      "price_extra": v.price_extra} for v in p.variants],
    }


def plan_out(p):
    return {
        "id": p.id, "name": p.name, "product_id": p.product_id, "price": p.price,
        "billing_period": p.billing_period.value, "min_quantity": p.min_quantity,
        "available_from": p.available_from, "available_to": p.available_to,
        "end_behavior": p.end_behavior.value, "is_active": p.is_active,
    }


def template_out(t):
    return {"id": t.id, "name": t.name, "plan_id": t.plan_id,
            "validity_days": t.validity_days, "is_active": t.is_active}


def discount_out(d):
    return {
        "id": d.id, "name": d.name, "kind": d.kind.value, "value": d.value,
        "scope": d.scope.value, "product_id": d.product_id, "min_purchase": d.min_purchase,
        "min_quantity": d.min_quantity, "start_date": d.start_date, "end_date": d.end_date,
        "usage_limit": d.usage_limit, "used_count": d.used_count, "is_active": d.is_active,
    }


def sub_out(s, detail=False):
    data = {
        "id": s.id, "number": s.number, "status": s.status.value,
        "customer_id": s.customer_id, "plan_id": s.plan_id, "template_id": s.template_id,
        "discount_id": s.discount_id, "quantity": s.quantity,
        "start_date": s.start_date, "expiry_date": s.expiry_date,
        "next_billing_date": s.next_billing_date, "payment_terms_days": s.payment_terms_days,
        "quotation_valid_until": s.quotation_valid_until,
    }
    if detail:
        data["lines"] = [{"id": l.id, "product_id": l.product_id, "description": l.description,
                          "quantity": l.quantity, "unit_price": l.unit_price, "tax_id": l.tax_id}
                         for l in s.lines]
        data["history"] = [{"from": l.from_status.value if l.from_status else None,
                            "to": l.to_status.value, "changed_by_id": l.changed_by_id,
                            "changed_at": l.changed_at} for l in s.status_logs]
    return data


def payment_out(p):
    return {"id": p.id, "invoice_id": p.invoice_id, "method": p.method.value,
            "amount": p.amount, "paid_on": p.paid_on, "note": p.note,
            "recorded_by_id": p.recorded_by_id}


def invoice_out(inv, detail=False):
    data = {
        "id": inv.id, "number": inv.number, "status": inv.status.value,
        "subscription_id": inv.subscription_id, "customer_id": inv.customer_id,
        "discount_id": inv.discount_id, "period_start": inv.period_start,
        "period_end": inv.period_end, "invoice_date": inv.invoice_date, "due_date": inv.due_date,
        "subtotal": inv.subtotal, "discount_total": inv.discount_total,
        "tax_total": inv.tax_total, "total": inv.total, "amount_paid": inv.amount_paid,
        "balance": inv.total - inv.amount_paid, "sent_at": inv.sent_at,
    }
    if detail:
        data["lines"] = [{"id": l.id, "description": l.description, "quantity": l.quantity,
                          "unit_price": l.unit_price, "subtotal": l.subtotal,
                          "discount_amount": l.discount_amount, "tax_rate": l.tax_rate,
                          "tax_amount": l.tax_amount, "line_total": l.line_total}
                         for l in inv.lines]
        data["payments"] = [payment_out(p) for p in inv.payments]
        data["customer"] = {"id": inv.customer.id, "full_name": inv.customer.full_name,
                            "email": inv.customer.email}
        data["subscription_number"] = inv.subscription.number
        data["plan_name"] = inv.subscription.plan.name
        data["company_name"] = settings.company_name
    return data


def run_out(r):
    return {"id": r.id, "run_date": r.run_date, "started_at": r.started_at,
            "finished_at": r.finished_at, "invoices_created": r.invoices_created,
            "subscriptions_skipped": r.subscriptions_skipped,
            "errors": json.loads(r.errors) if r.errors else []}
