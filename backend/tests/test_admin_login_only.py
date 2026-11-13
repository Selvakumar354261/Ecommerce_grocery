from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import User
from app.security import hash_password

PASSWORD='DemoGrocery!2026'

def test_only_admin_can_sign_in_when_admin_login_only(monkeypatch):
    with SessionLocal.begin() as db:
        db.add(User(name='Driver',email='driver-only@example.com',password_hash=hash_password(PASSWORD),role='delivery',branch_id=1))
    # A manager session created before the switch must stop working afterwards.
    manager=TestClient(app)
    assert manager.post('/api/v1/auth/login',json={'email':'manager@gmail.com','password':PASSWORD}).status_code==200
    monkeypatch.setenv('ADMIN_LOGIN_ONLY','true')
    client=TestClient(app)

    admin=client.post('/api/v1/auth/login',json={'email':'admin@gmail.com','password':PASSWORD})
    assert admin.status_code==200 and admin.json()['user']['role']=='admin'
    assert client.get('/api/v1/auth/session').json()['user']['role']=='admin'

    assert manager.get('/api/v1/auth/session').json()['user'] is None
    assert manager.get('/api/v1/delivery/profile').status_code==401
    for email in ('manager@gmail.com','cashier@gmail.com','inventory@gmail.com'):
        assert TestClient(app).post('/api/v1/auth/login',json={'email':email,'password':PASSWORD}).status_code==403
    assert TestClient(app).post('/api/v1/auth/otp/request',json={'phone':'9876543210'}).status_code==403
    assert TestClient(app).post('/api/v1/auth/otp/verify',json={'phone':'9876543210','otp':'123456'}).status_code==403
    assert TestClient(app).post('/api/v1/auth/register',json={'name':'New Customer','email':'new@example.com','password':'LongPassword123!'}).status_code==403
    assert TestClient(app).post('/api/v1/delivery/auth/login',json={'email':'driver-only@example.com','password':PASSWORD}).status_code==403
