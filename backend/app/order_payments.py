"""Authoritative settlement of online orders, including mixed tenders."""
from decimal import Decimal
from fastapi import HTTPException

from .models import Order, OrderCollection, OrderEvent, User
from .security import scope
from .services import audit, get_or_404, money


def collection_order(db, user, ident, lock=False):
    order = get_or_404(db, Order, ident, lock)
    if user.role == 'delivery':
        if order.assigned_delivery_user_id != user.id or order.method != 'delivery':
            raise HTTPException(404, 'Delivery not found.')
        if order.status != 'dispatched' and not (order.status == 'completed' and order.payment_status == 'paid'):
            raise HTTPException(409, 'Start the delivery before collecting payment.')
    else:
        scope(user, order.branch_id, ('admin', 'manager'))
        if order.status not in ('ready', 'dispatched') and not (order.status == 'completed' and order.payment_status == 'paid'):
            raise HTTPException(409, 'Record collection at handover or delivery.')
    return order


def settlement_quote(order, data):
    total = money(order.total)
    if data.expected_total is not None and data.expected_total != total:
        raise HTTPException(409, 'The order total changed. Refresh and review the payment again.')
    if data.payment_method == 'split':
        if len(data.payments) < 2:
            raise HTTPException(422, 'Split payment requires at least two payment methods.')
        allocations = {payment.method: money(payment.amount) for payment in data.payments}
        if len(allocations) != len(data.payments):
            raise HTTPException(422, 'Each payment method can be used only once.')
        if sum(allocations.values(), Decimal(0)) != total:
            raise HTTPException(422, 'Split payment amounts must exactly equal the order total.')
    else:
        if data.payments:
            raise HTTPException(422, 'A payment breakdown is only accepted for split payments.')
        allocations = {data.payment_method: total}
    cash = allocations.get('cash', Decimal(0))
    if data.payment_method == 'split':
        if data.amount_tendered is not None and data.amount_tendered != cash:
            raise HTTPException(422, 'For split payments, cash collected must equal the cash portion; no change is calculated.')
        tendered, change = (money(cash) if cash else None), Decimal('0.00')
    elif cash:
        if data.amount_tendered is None:
            raise HTTPException(422, 'Enter the actual cash received from the customer.')
        if data.amount_tendered < cash:
            raise HTTPException(422, 'Cash received cannot be less than the cash portion.')
        tendered = money(data.amount_tendered)
        change = money(tendered - cash)
    else:
        if data.amount_tendered is not None:
            raise HTTPException(422, 'Cash received is only used when a cash portion exists.')
        tendered, change = None, Decimal('0.00')
    return {
        'payment_method': data.payment_method, 'total': str(total),
        'payments': [{'method': method, 'amount': str(allocations[method])} for method in ('cash', 'card', 'upi') if method in allocations],
        'cash_portion': str(money(cash)), 'amount_tendered': str(tendered) if tendered is not None else None,
        'change_due': str(money(change)),
    }


def collection_view(db, order):
    record = db.get(OrderCollection, order.id)
    if not record:
        return None
    actor = db.get(User, record.actor_id)
    return {
        'payment_method': record.payment_method, 'payments': record.payments,
        'total': str(record.total), 'amount_tendered': str(record.amount_tendered) if record.amount_tendered is not None else None,
        'change_due': str(record.change_due), 'collected_at': record.created_at,
        'collected_by': actor.name if actor else 'Unknown',
    }


def record_collection(db, user, order, data):
    quote = settlement_quote(order, data)
    if order.payment_status == 'paid':
        recorded = collection_view(db, order)
        fields = ('payment_method', 'payments', 'total', 'amount_tendered', 'change_due')
        if recorded and all(recorded[field] == quote[field] for field in fields):
            return recorded  # A transport retry must not collect twice or duplicate history.
        raise HTTPException(409, 'Payment is already recorded. Refresh the order; existing collections cannot be overwritten.')
    db.add(OrderCollection(
        order_id=order.id, actor_id=user.id, payment_method=quote['payment_method'], payments=quote['payments'],
        total=order.total, amount_tendered=Decimal(quote['amount_tendered']) if quote['amount_tendered'] is not None else None,
        change_due=Decimal(quote['change_due']),
    ))
    order.payment_status = 'paid'
    breakdown = ', '.join(f"{part['method'].upper()} INR {part['amount']}" for part in quote['payments'])
    cash_note = f" Cash received INR {quote['amount_tendered']}; change returned INR {quote['change_due']}." if quote['amount_tendered'] is not None else ''
    db.add(OrderEvent(order_id=order.id, status='payment_received', actor_id=user.id, note=f'Payment collected: {breakdown}.{cash_note}'))
    audit(db, user, 'order.payment_collected', order.id, **quote)
    db.flush()
    return collection_view(db, order)
