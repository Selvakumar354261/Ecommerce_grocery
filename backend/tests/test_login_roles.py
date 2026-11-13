from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import User
from app.security import hash_password

PASSWORD='DemoGrocery!2026'

def test_only_listed_roles_can_sign_in(monkeypatch):
    with SessionLocal.begin() as db:
        db.add(User(name='Driver',email='driver-only@example.com',password_hash=hash_password(PASSWORD),role='delivery',branch_id=1))
    # A cashier session created before the restriction must stop working afterwards.
    cashier=TestClient(app)
    assert cashier.post('/api/v1/auth/login',json={'email':'cashier@gmail.com','password':PASSWORD}).status_code==200
    monkeypatch.setenv('LOGIN_ROLES','manager')  # admin is always allowed even when not listed

    admin=TestClient(app)
    assert admin.post('/api/v1/auth/login',json={'email':'admin@gmail.com','password':PASSWORD}).status_code==200
    assert admin.get('/api/v1/auth/session').json()['user']['role']=='admin'
    manager=TestClient(app)
    assert manager.post('/api/v1/auth/login',json={'email':'manager@gmail.com','password':PASSWORD}).status_code==200
    assert manager.get('/api/v1/auth/session').json()['user']['role']=='manager'

    assert cashier.get('/api/v1/auth/session').json()['user'] is None
    assert cashier.get('/api/v1/delivery/profile').status_code==401
    for email in ('cashier@gmail.com','inventory@gmail.com'):
        assert TestClient(app).post('/api/v1/auth/login',json={'email':email,'password':PASSWORD}).status_code==403
    assert TestClient(app).post('/api/v1/auth/otp/request',json={'phone':'9876543210'}).status_code==403
    assert TestClient(app).post('/api/v1/auth/otp/verify',json={'phone':'9876543210','otp':'123456'}).status_code==403
    assert TestClient(app).post('/api/v1/auth/register',json={'name':'New Customer','email':'new@example.com','password':'LongPassword123!'}).status_code==403
    assert TestClient(app).post('/api/v1/delivery/auth/login',json={'email':'driver-only@example.com','password':PASSWORD}).status_code==403

def test_customer_role_enables_otp(monkeypatch):
    monkeypatch.setenv('LOGIN_ROLES','admin,customer')
    client=TestClient(app)
    requested=client.post('/api/v1/auth/otp/request',json={'phone':'9876543211'})
    assert requested.status_code==200
    verified=client.post('/api/v1/auth/otp/verify',json={'phone':'9876543211','otp':requested.json()['development_otp'],'name':'New Customer'})
    assert verified.status_code==200 and verified.json()['user']['role']=='customer'
    assert client.get('/api/v1/auth/session').json()['user']['role']=='customer'
