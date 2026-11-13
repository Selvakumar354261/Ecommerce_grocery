from fastapi.testclient import TestClient
from app.main import app

def customer(phone):
    client=TestClient(app)
    request=client.post('/api/v1/auth/otp/request',json={'phone':phone}).json()
    result=client.post('/api/v1/auth/otp/verify',json={'phone':phone,'otp':request['development_otp'],'name':'Test customer'})
    assert result.status_code==200,result.text
    client.headers['X-CSRF-Token']=result.json()['csrf']
    return client

def test_saved_locations_validation_and_ownership():
    first=customer('9876543210');second=customer('9876543211')
    body={'label':'Home','address':'Complete delivery address','phone':'9876543212','latitude':'11.3410000','longitude':'77.7172000'}
    saved=first.post('/api/v1/customer/addresses',json=body)
    assert saved.status_code==201,saved.text
    ident=saved.json()['id']
    assert saved.json()['phone']=='9876543212'
    assert first.post('/api/v1/customer/addresses',json={**body,'phone':'123'}).status_code==422
    assert len(first.get('/api/v1/customer/addresses').json())==1
    assert second.get('/api/v1/customer/addresses').json()==[]
    assert second.put(f'/api/v1/customer/addresses/{ident}',json=body).status_code==404
    assert second.delete(f'/api/v1/customer/addresses/{ident}').status_code==404
    changed=first.put(f'/api/v1/customer/addresses/{ident}',json={**body,'label':'Farm','latitude':'12.1'})
    assert changed.status_code==200 and changed.json()['label']=='Farm'
    assert first.post('/api/v1/customer/addresses',json={**body,'latitude':'91'}).status_code==422
    assert first.post('/api/v1/customer/addresses',json={**body,'address':'        '}).status_code==422
    assert TestClient(app).get('/api/v1/customer/addresses').status_code==401
    assert first.delete(f'/api/v1/customer/addresses/{ident}').status_code==200
    assert first.get('/api/v1/customer/addresses').json()==[]
