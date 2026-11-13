from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import SessionLocal
from app.models import User,Order
from app.security import hash_password

def test_driver_profile_and_history_are_private_and_paginated():
    with SessionLocal.begin() as db:
        customer=db.scalar(select(User).where(User.role=='customer'))
        driver=User(name='Driver',email='driver-test@example.com',password_hash=hash_password('DriverPassword123'),role='delivery',branch_id=1)
        other=User(name='Other',email='other-driver@example.com',password_hash=hash_password('DriverPassword123'),role='delivery',branch_id=1)
        db.add_all([driver,other]);db.flush()
        for owner,status in [(driver,'completed'),(driver,'ready'),(other,'completed')]:
            db.add(Order(user_id=customer.id,branch_id=1,method='delivery',address='Test delivery address',phone='9876543210',status=status,subtotal=Decimal('100'),delivery_fee=0,total=100,pickup_code='123456',assigned_delivery_user_id=owner.id))
    client=TestClient(app)
    token=client.post('/api/v1/delivery/auth/login',json={'email':'driver-test@example.com','password':'DriverPassword123'}).json()['token']
    client.headers['Authorization']='Bearer '+token
    profile=client.get('/api/v1/delivery/profile')
    assert profile.status_code==200 and profile.json()['name']=='Driver'
    assert profile.json()['completed']==1 and profile.json()['active']==1
    history=client.get('/api/v1/delivery/history').json()
    assert history['total']==1 and len(history['items'])==1
    assert history['items'][0]['status']=='completed'
    assert client.get('/api/v1/delivery/history?status=cancelled').json()['total']==0
    assert client.get('/api/v1/delivery/history?page=2').json()['items']==[]
    assert client.get('/api/v1/delivery/history?status=bad').status_code==422
    assert TestClient(app).get('/api/v1/delivery/profile').status_code==401
