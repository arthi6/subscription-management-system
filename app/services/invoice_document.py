"""Renders an invoice as a standalone, print-ready HTML document (A4).

Data comes from ``serializers.invoice_out(detail=True)`` so the printed invoice always matches the
JSON API. Every dynamic value is passed through ``html.escape`` before it is placed in markup;
nothing user-supplied is ever concatenated into the page unescaped.
"""
from datetime import date, datetime
from decimal import Decimal
from html import escape

from app.serializers import invoice_out

_STYLE = """
@page { size: A4; margin: 16mm; }
* { box-sizing: border-box; }
body { font-family: Helvetica, Arial, sans-serif; color: #1f2933; font-size: 13px; line-height: 1.45; margin: 0; }
.sheet { max-width: 794px; margin: 0 auto; padding: 24px; }
header { display: flex; justify-content: space-between; align-items: flex-start;
         border-bottom: 3px solid #1f4e79; padding-bottom: 14px; margin-bottom: 20px; }
h1 { font-size: 26px; letter-spacing: 2px; margin: 0; color: #1f4e79; }
.company { font-size: 18px; font-weight: 700; }
.meta { text-align: right; }
.status { display: inline-block; margin-top: 6px; padding: 2px 10px; border: 1px solid #1f4e79;
          border-radius: 3px; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #1f4e79; }
.status.cancelled { color: #b42318; border-color: #b42318; }
.status.paid { color: #067647; border-color: #067647; }
.cols { display: flex; gap: 24px; margin-bottom: 20px; }
.cols > div { flex: 1; }
h2 { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #667085; margin: 0 0 6px; }
dl { margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 3px 12px; }
dt { color: #667085; }
dd { margin: 0; }
table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
th { background: #1f4e79; color: #fff; text-align: left; font-size: 11px; text-transform: uppercase;
     letter-spacing: .5px; padding: 7px 8px; }
td { padding: 7px 8px; border-bottom: 1px solid #e4e7ec; vertical-align: top; }
.num { text-align: right; white-space: nowrap; }
tbody tr { page-break-inside: avoid; }
.totals { width: 55%; margin-left: auto; }
.totals td { border-bottom: 1px solid #e4e7ec; }
.totals tr.grand td { font-weight: 700; font-size: 15px; border-top: 2px solid #1f4e79; }
.totals tr.balance td { font-weight: 700; background: #eef4fa; }
footer { margin-top: 28px; padding-top: 10px; border-top: 1px solid #e4e7ec; color: #667085; font-size: 11px; }
@media print { .sheet { padding: 0; } }
"""


def _e(value) -> str:
    """Escape any value for HTML text and attribute contexts. None becomes an em dash."""
    if value is None or value == "":
        return "&mdash;"
    return escape(str(value), quote=True)


def _money(value) -> str:
    return escape(f"{Decimal(value):,.2f}")


def _date(value) -> str:
    if isinstance(value, (date, datetime)):
        return escape(value.strftime("%d %b %Y"))
    return _e(value)


def invoice_title(data: dict) -> str:
    """Invoice number, or a placeholder for drafts that have not been numbered yet."""
    return data["number"] or f"DRAFT-{data['id']}"


def render_invoice_html(inv) -> str:
    data = invoice_out(inv, detail=True)
    title = invoice_title(data)
    customer = data["customer"]
    status = data["status"]

    rows = []
    for ln in data["lines"]:
        rows.append(
            "<tr>"
            f"<td>{_e(ln['description'])}</td>"
            f"<td class='num'>{_e(ln['quantity'])}</td>"
            f"<td class='num'>{_money(ln['unit_price'])}</td>"
            f"<td class='num'>{_money(ln['subtotal'])}</td>"
            f"<td class='num'>{_money(ln['discount_amount'])}</td>"
            f"<td class='num'>{_e(ln['tax_rate'])}%</td>"
            f"<td class='num'>{_money(ln['tax_amount'])}</td>"
            f"<td class='num'>{_money(ln['line_total'])}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='8'>No line items</td></tr>")

    payment_rows = "".join(
        "<tr>"
        f"<td>{_date(p['paid_on'])}</td>"
        f"<td>{_e(p['method'].replace('_', ' ').title())}</td>"
        f"<td>{_e(p['note'])}</td>"
        f"<td class='num'>{_money(p['amount'])}</td>"
        "</tr>"
        for p in data["payments"]
    )
    payments_block = (
        "<h2>Payments received</h2><table><thead><tr><th>Date</th><th>Method</th><th>Note</th>"
        f"<th class='num'>Amount</th></tr></thead><tbody>{payment_rows}</tbody></table>"
        if payment_rows else ""
    )

    discount_cell = ("-" if Decimal(data["discount_total"]) else "") + _money(data["discount_total"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Invoice {_e(title)} - {_e(data['company_name'])}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="sheet">
<header>
  <div><div class="company">{_e(data['company_name'])}</div></div>
  <div class="meta">
    <h1>INVOICE</h1>
    <div><strong>{_e(title)}</strong></div>
    <span class="status {escape(status)}">{_e(status)}</span>
  </div>
</header>

<div class="cols">
  <div>
    <h2>Bill to</h2>
    <div><strong>{_e(customer['full_name'])}</strong></div>
    <div>{_e(customer['email'])}</div>
  </div>
  <div>
    <h2>Invoice details</h2>
    <dl>
      <dt>Issue date</dt><dd>{_date(data['invoice_date'])}</dd>
      <dt>Due date</dt><dd>{_date(data['due_date'])}</dd>
      <dt>Billing period</dt><dd>{_date(data['period_start'])} &ndash; {_date(data['period_end'])}</dd>
      <dt>Subscription</dt><dd>{_e(data['subscription_number'])}</dd>
      <dt>Plan</dt><dd>{_e(data['plan_name'])}</dd>
    </dl>
  </div>
</div>

<table>
  <thead><tr>
    <th>Description</th><th class="num">Qty</th><th class="num">Unit price</th>
    <th class="num">Amount</th><th class="num">Discount</th><th class="num">Tax rate</th>
    <th class="num">Tax</th><th class="num">Line total</th>
  </tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>

<table class="totals">
  <tr><td>Subtotal</td><td class="num">{_money(data['subtotal'])}</td></tr>
  <tr><td>Discount</td><td class="num">{discount_cell}</td></tr>
  <tr><td>Tax</td><td class="num">{_money(data['tax_total'])}</td></tr>
  <tr class="grand"><td>Total</td><td class="num">{_money(data['total'])}</td></tr>
  <tr><td>Amount paid</td><td class="num">{_money(data['amount_paid'])}</td></tr>
  <tr class="balance"><td>Balance due</td><td class="num">{_money(data['balance'])}</td></tr>
</table>

{payments_block}
<footer>{_e(data['company_name'])} &middot; Payment is due by {_date(data['due_date'])}. Thank you for your business.</footer>
</div>
</body>
</html>
"""
