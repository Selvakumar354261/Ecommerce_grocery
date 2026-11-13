from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Order, OrderEvent, User, now
from conftest import login


def setup_report():
    admin, manager, customer = login(), login('manager@grove.local'), login('customer@grove.local')
    with SessionLocal.begin() as db:
        admin_user = db.scalar(select(User).where(User.email == 'admin@grove.local'))
        customer_user = db.scalar(select(User).where(User.email == 'customer@grove.local'))
        driver = User(name='DRIVER ONE', email='report-driver@chinnu.local', role='delivery', branch_id=1, active=True)
        other_driver = User(name='DRIVER TWO', email='other-report-driver@chinnu.local', role='delivery', branch_id=2, active=True)
        db.add_all([driver, other_driver]); db.flush()
        ids = {}
        stamp = now() - timedelta(hours=2)
        def make(name, status, assigned=True, branch=1, method='delivery', created_at=stamp):
            order = Order(user_id=customer_user.id, branch_id=branch, method=method, address='REPORT ADDRESS', phone='9876543210',
                          status=status, subtotal=Decimal('100'), delivery_fee=Decimal('30'), total=Decimal('130'),
                          pickup_code='654321', reserved_active=status == 'ready',
                          assigned_delivery_user_id=(driver.id if branch == 1 else other_driver.id) if assigned else None,
                          delivery_assigned_at=stamp if assigned else None, created_at=created_at,
                          payment_status='paid' if status == 'completed' else 'unpaid')
            db.add(order); db.flush(); ids[name] = order.id
            return order
        def event(order, status, actor=driver, minutes=0):
            db.add(OrderEvent(order_id=order.id, status=status, actor_id=actor.id if actor else None,
                              note=f'{status} reason', created_at=stamp + timedelta(minutes=minutes)))
            db.flush()
        make('unassigned', 'ready', False)
        make('waiting', 'ready')
        active = make('active', 'dispatched'); event(active, 'dispatched')
        failed = make('failed', 'dispatched'); event(failed, 'dispatched'); event(failed, 'delivery_failed', minutes=10); event(failed, 'delivery_failed', minutes=20)
        completed = make('completed', 'completed'); event(completed, 'dispatched'); event(completed, 'delivery_failed', minutes=5); event(completed, 'completed', minutes=30)
        cancelled = make('cancelled', 'cancelled'); event(cancelled, 'cancelled', customer_user)
        rejected = make('rejected', 'cancelled'); event(rejected, 'cancelled', admin_user)  # Legacy store rejection.
        expired = make('expired', 'cancelled', False); event(expired, 'cancelled', None)
        make('pickup', 'completed', method='pickup')
        remote = make('other_branch', 'completed', branch=2); event(remote, 'completed', other_driver)
        # An old job still contributes to current workload even when excluded from the report period.
        make('old_active', 'dispatched', created_at=stamp - timedelta(days=20))
        return admin, manager, customer, driver.id, other_driver.id, ids, stamp


def test_delivery_report_counts_failures_outcomes_pagination_and_branch_access():
    admin, manager, customer, driver_id, other_driver_id, ids, stamp = setup_report()
    report = manager.get('/api/v1/delivery/operations').json()
    assert report['summary'] == {'all': 9, 'awaiting_ready': 0, 'unassigned': 1, 'assigned': 1,
                                 'in_transit': 2, 'unsuccessful': 1, 'completed': 1, 'cancelled': 1,
                                 'rejected': 1, 'expired': 1, 'failed_attempts': 3}
    performance = next(person for person in report['drivers'] if person['id'] == driver_id)
    assert performance['total_assigned'] == 7 and performance['assigned'] == 1
    assert performance['current_workload'] == 4 and performance['completed'] == 1
    assert performance['unsuccessful'] == 1 and performance['failed_attempts'] == 3
    assert performance['cancelled'] == 1 and performance['rejected'] == 1
    assert performance['average_trip_minutes'] == 30
    assert all(person['id'] != other_driver_id for person in report['drivers'])
    assert ids['pickup'] not in [row['id'] for row in report['orders']]
    assert admin.get('/api/v1/delivery/operations').json()['summary']['all'] == 10
    assert manager.get('/api/v1/delivery/operations?branch_id=2').status_code == 403
    assert manager.get(f'/api/v1/delivery/operations?driver_id={other_driver_id}').status_code == 404
    assert manager.get(f"/api/v1/delivery/operations/{ids['other_branch']}").status_code == 403
    assert customer.get('/api/v1/delivery/operations').status_code == 403
    assert customer.get(f"/api/v1/delivery/operations/{ids['active']}").status_code == 403
    page = manager.get('/api/v1/delivery/operations?page_size=2&page=2').json()
    assert page['total'] == 9 and page['pages'] == 5 and len(page['orders']) == 2
    failed = manager.get('/api/v1/delivery/operations?status=unsuccessful').json()
    assert failed['total'] == 1 and failed['orders'][0]['id'] == ids['failed']
    assert failed['summary']['all'] == 9  # Status tabs retain the full scoped counts.
    assert manager.get('/api/v1/delivery/operations?status=unknown').status_code == 422
    assert manager.get('/api/v1/delivery/operations?page=0').status_code == 422


def test_delivery_report_dates_search_detail_and_safe_assignment():
    admin, manager, _, driver_id, other_driver_id, ids, stamp = setup_report()
    india_date = stamp.astimezone(timezone(timedelta(hours=5, minutes=30))).date()
    params = {'from_date': str(india_date), 'to_date': str(india_date), 'driver_id': driver_id}
    report = manager.get('/api/v1/delivery/operations', params=params).json()
    assert report['summary']['all'] == 6
    person = next(value for value in report['drivers'] if value['id'] == driver_id)
    assert person['current_workload'] == 4 and person['total_assigned'] == 6
    assert manager.get('/api/v1/delivery/operations?from_date=2026-11-04&to_date=2026-11-03').status_code == 422
    found = manager.get('/api/v1/delivery/operations', params={'search': f"ORD-{ids['completed']:06d}"}).json()
    assert found['total'] == 1 and found['orders'][0]['id'] == ids['completed']
    assert manager.get('/api/v1/delivery/operations', params={'search': '%'}).json()['total'] == 0
    detail = manager.get(f"/api/v1/delivery/operations/{ids['failed']}").json()
    assert detail['failed_attempts'] == 2 and detail['last_issue'] == 'delivery_failed reason'
    assert detail['history'][-1]['actor_name'] == 'DRIVER ONE'
    assert 'pickup_code' not in detail  # Managers and drivers must not see customer verification codes.
    assert detail['available_drivers'] == [{'id': driver_id, 'name': 'DRIVER ONE', 'current_workload': 4}]
    assert manager.get(f"/api/v1/delivery/operations/{ids['pickup']}").status_code == 409
    assigned = manager.post(f"/api/v1/orders/{ids['unassigned']}/assign-delivery", json={'delivery_user_id': driver_id})
    assert assigned.status_code == 200
    again = manager.post(f"/api/v1/orders/{ids['unassigned']}/assign-delivery", json={'delivery_user_id': driver_id})
    assert again.status_code == 200
    detail = manager.get(f"/api/v1/delivery/operations/{ids['unassigned']}").json()
    assert detail['driver_id'] == driver_id and detail['delivery_state'] == 'assigned'
    assert len([event for event in detail['history'] if event['status'] == 'delivery_assigned']) == 1
    assert manager.post(f"/api/v1/orders/{ids['waiting']}/assign-delivery", json={'delivery_user_id': other_driver_id}).status_code == 422
    assert admin.post(f"/api/v1/orders/{ids['active']}/assign-delivery", json={'delivery_user_id': driver_id}).status_code == 409
    assert manager.post(f"/api/v1/orders/{ids['active']}/payment", json={'payment_method':'cash','amount_tendered':'200.00'}).status_code == 200
    detail = manager.get(f"/api/v1/delivery/operations/{ids['active']}").json()
    collection = next(event for event in detail['history'] if event['status'] == 'payment_received')
    assert collection['actor_role'] == 'manager' and '130.00' in collection['note']


def test_delivery_report_uses_indian_date_boundaries():
    admin, manager, _, _, _, ids, _ = setup_report()
    with SessionLocal.begin() as db:
        order = db.get(Order, ids['unassigned'])
        order.created_at = datetime(2026, 11, 2, 18, 30, tzinfo=timezone.utc)  # Midnight Nov 3 in India.
    rows = manager.get('/api/v1/delivery/operations?from_date=2026-11-03&to_date=2026-11-03').json()['orders']
    assert ids['unassigned'] in [row['id'] for row in rows]
    with SessionLocal.begin() as db:
        db.get(Order, ids['unassigned']).created_at -= timedelta(microseconds=1)
    rows = manager.get('/api/v1/delivery/operations?from_date=2026-11-03&to_date=2026-11-03').json()['orders']
    assert ids['unassigned'] not in [row['id'] for row in rows]
