import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.db import SessionLocal, engine
from app.main import app
from sample_data import main as seed

@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setenv('SEED_ADMIN_ONLY','false')
    assert engine.url.database=='grocery_test','Tests require the isolated grocery_test database.'
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE '+','.join('"'+t+'"' for t in __import__('app.models',fromlist=['Base']).Base.metadata.tables)+' RESTART IDENTITY CASCADE'))
    os.environ['DEMO_PASSWORD']='DemoGrocery!2026'
    seed()

def login(email='admin@grove.local'):
    client=TestClient(app)
    if email=='customer@grove.local':
        requested=client.post('/api/v1/auth/otp/request',json={'phone':'9876543210'}).json()
        r=client.post('/api/v1/auth/otp/verify',json={'phone':'9876543210','otp':requested['development_otp'],'name':'Demo Customer','email':email})
    else:
        r=client.post('/api/v1/auth/login',json={'email':email,'password':'DemoGrocery!2026'})
    assert r.status_code==200,r.text
    client.headers['X-CSRF-Token']=r.json()['csrf']
    if r.json()['user']['role'] in ('admin','manager','cashier'):
        from uuid import uuid4
        branch=r.json()['user']['branch_id'] or 1
        client.post('/api/v1/shifts/open',json={'branch_id':branch,'cash':'0'},headers={'Idempotency-Key':str(uuid4())})
    return client
