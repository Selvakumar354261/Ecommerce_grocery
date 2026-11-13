import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.db import SessionLocal
from app.main import app
from app.models import Order, OrderCollection, OrderEvent, User
from app.security import hash_password
from test_delivery_reporting import setup_report


def driver_session(driver_id):
    with SessionLocal.begin() as db:
        db.get(User, driver_id).password_hash = hash_password('DriverPass!2026')
    token = TestClient(app).post('/api/v1/delivery/auth/login', json={'email':'report-driver@chinnu.local','password':'DriverPass!2026'}).json()['token']
    return TestClient(app, headers={'Authorization': f'Bearer {token}'})


def test_cash_collection_preview_persistence_change_and_immutable_retry():
    admin, manager, customer, driver_id, _, ids, _ = setup_report()
    mobile = driver_session(driver_id); ident = ids['active']
    payload = {'payment_method':'cash','amount_tendered':'200.00'}
    preview = mobile.post(f'/api/v1/orders/{ident}/payment/preview', json=payload)
    assert preview.status_code == 200 and preview.json()['change_due'] == '70.00'
    with SessionLocal() as db:
        assert db.get(Order, ident).payment_status == 'unpaid' and db.get(OrderCollection, ident) is None
    recorded = mobile.post(f'/api/v1/orders/{ident}/payment', json={**payload, 'expected_total':'130.00'})
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()['payments'] == [{'method':'cash','amount':'130.00'}]
    assert recorded.json()['amount_tendered'] == '200.00' and recorded.json()['change_due'] == '70.00'
    assert mobile.post(f'/api/v1/orders/{ident}/payment', json=payload).status_code == 200
    assert mobile.post(f'/api/v1/orders/{ident}/payment', json={'payment_method':'upi'}).status_code == 409
    assert mobile.post(f'/api/v1/orders/{ident}/payment/preview', json=payload).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OrderCollection).where(OrderCollection.order_id == ident)) == 1
        assert db.scalar(select(func.count()).select_from(OrderEvent).where(OrderEvent.order_id == ident, OrderEvent.status == 'payment_received')) == 1
    customer_view = customer.get(f'/api/v1/orders/{ident}').json()
    assert customer_view['payment_collection']['change_due'] == '70.00'
    assert manager.get(f'/api/v1/delivery/operations/{ident}').json()['payment_collection']['collected_by'] == 'DRIVER ONE'
    assert mobile.post(f'/api/v1/delivery/orders/{ident}/complete', json={'otp':'654321'}, headers={'Idempotency-Key':'complete-test'}).status_code == 200
    assert mobile.post(f'/api/v1/orders/{ident}/payment', json=payload).status_code == 200  # Safe late network retry.


@pytest.mark.parametrize('payload,change', [
    ({'payment_method':'upi'}, '0.00'),
    ({'payment_method':'card'}, '0.00'),
    ({'payment_method':'split','payments':[{'method':'cash','amount':'50.00'},{'method':'upi','amount':'80.00'}]}, '0.00'),
    ({'payment_method':'split','payments':[{'method':'card','amount':'50.00'},{'method':'upi','amount':'80.00'}]}, '0.00'),
    ({'payment_method':'split','payments':[{'method':'cash','amount':'30.01'},{'method':'card','amount':'49.99'},{'method':'upi','amount':'50.00'}]}, '0.00'),
])
def test_digital_and_split_collections_are_exactly_persisted(payload, change):
    _, manager, _, _, _, ids, _ = setup_report(); ident = ids['active']
    result = manager.post(f'/api/v1/orders/{ident}/payment', json=payload)
    assert result.status_code == 200, result.text
    assert result.json()['payment_method'] == payload['payment_method'] and result.json()['change_due'] == change
    saved = manager.get(f'/api/v1/orders/{ident}').json()['payment_collection']
    assert saved['payments'] == result.json()['payments']


@pytest.mark.parametrize('payload', [
    {}, {'payment_method':'cash'}, {'payment_method':'cash','amount_tendered':'129.99'},
    {'payment_method':'cash','amount_tendered':'-1'}, {'payment_method':'cash','amount_tendered':'200.001'},
    {'payment_method':'upi','amount_tendered':'10.00'},
    {'payment_method':'split','payments':[{'method':'cash','amount':'130'}],'amount_tendered':'130'},
    {'payment_method':'split','payments':[{'method':'cash','amount':'50'},{'method':'cash','amount':'80'}],'amount_tendered':'130'},
    {'payment_method':'split','payments':[{'method':'card','amount':'50'},{'method':'upi','amount':'79.99'}]},
    {'payment_method':'split','payments':[{'method':'card','amount':'50'},{'method':'upi','amount':'80.01'}]},
    {'payment_method':'split','payments':[{'method':'card','amount':'0'},{'method':'upi','amount':'130'}]},
])
def test_invalid_collection_does_not_mark_paid(payload):
    _, manager, _, _, _, ids, _ = setup_report(); ident = ids['active']
    assert manager.post(f'/api/v1/orders/{ident}/payment', json=payload).status_code == 422
    with SessionLocal() as db:
        assert db.get(Order, ident).payment_status == 'unpaid' and db.get(OrderCollection, ident) is None


def test_collection_role_assignment_status_and_stale_total_are_backend_validated():
    _, manager, customer, driver_id, _, ids, _ = setup_report(); mobile = driver_session(driver_id)
    payload = {'payment_method':'upi'}
    for route in ('payment', 'payment/preview'):
        assert customer.post(f"/api/v1/orders/{ids['active']}/{route}", json=payload).status_code == 403
        assert manager.post(f"/api/v1/orders/{ids['other_branch']}/{route}", json=payload).status_code == 403
        assert mobile.post(f"/api/v1/orders/{ids['other_branch']}/{route}", json=payload).status_code == 404
        assert mobile.post(f"/api/v1/orders/{ids['waiting']}/{route}", json=payload).status_code == 409
    assert manager.post(f"/api/v1/orders/{ids['active']}/payment", json={**payload,'expected_total':'129.00'}).status_code == 409
    # Never invent tender or change for historical paid orders.
    assert manager.get(f"/api/v1/orders/{ids['completed']}").json()['payment_collection'] is None
