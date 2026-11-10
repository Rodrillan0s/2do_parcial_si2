"""Exact refundable merchandise amounts using existing sale snapshots."""
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException


def cents(value):
    amount = Decimal(str(value or 0))
    if not amount.is_finite() or amount < 0:
        raise HTTPException(409, 'REFUND_RECONCILIATION_REQUIRED: importe inválido.')
    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def line_entitlements(rows, subtotal, discount, paid_total):
    """Allocate header discount once, with stable largest-remainder cents.

    Rows: (sale_line, variant, quantity, price, line_discount, line_subtotal).
    Shipping is never added to the refundable merchandise entitlement.
    """
    weights = {r[0]: cents(r[5]) for r in rows}
    if not rows or any(int(r[2]) <= 0 for r in rows):
        raise HTTPException(409, 'REFUND_RECONCILIATION_REQUIRED: detalle inválido.')
    gross, reduction, paid = cents(subtotal), cents(discount), cents(paid_total)
    if reduction > gross:
        raise HTTPException(409, 'REFUND_RECONCILIATION_REQUIRED: descuento mayor al subtotal.')
    target = min(gross - reduction, paid)
    weight_sum = sum(weights.values())
    if weight_sum not in (gross, gross - reduction):
        raise HTTPException(409, 'REFUND_RECONCILIATION_REQUIRED: cabecera y detalles no concuerdan.')
    if not weight_sum:
        return {key: 0 for key in weights}
    allocated = {key: target * value // weight_sum for key, value in weights.items()}
    order = sorted(weights, key=lambda key: (-(target * weights[key] % weight_sum), key))
    for key in order[:target - sum(allocated.values())]:
        allocated[key] += 1
    return allocated


def partial_amount(line_cents, original_quantity, previous_quantity, quantity):
    if min(original_quantity, quantity) <= 0 or previous_quantity < 0 or previous_quantity + quantity > original_quantity:
        raise HTTPException(400, 'Cantidad superior al saldo elegible.')
    amount = (line_cents * (previous_quantity + quantity) // original_quantity
              - line_cents * previous_quantity // original_quantity)
    return Decimal(amount) / Decimal(100)
