from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app
from app.schemas import CartIn, VariantIn, OrderIn
from app.security import hash_password, verify_password
from app.services import distance, money

def test_password_salt_and_verification():
    first=hash_password('A realistic password 123!')
    second=hash_password('A realistic password 123!')
    assert first!=second
    assert verify_password('A realistic password 123!',first)
    assert not verify_password('incorrect',first)

def test_cart_rejects_duplicate_variant_and_invalid_quantities():
    with pytest.raises(ValidationError):CartIn(items=[{'variant_id':1,'quantity':1},{'variant_id':1,'quantity':2}])
    for qty in ('0','-1','NaN','Infinity','0.0001'):
        with pytest.raises(ValidationError):CartIn(items=[{'variant_id':1,'quantity':qty}])

def test_pack_rejects_fractional_configuration():
    with pytest.raises(ValidationError):VariantIn(sku='PACK1',label='One sealed pack',unit='pack',price=10,min_qty='.5',step='.5')
    variant=VariantIn(sku='BULK1',label='Loose almonds',unit='kg',price='840.00',min_qty='.1',step='.05')
    assert variant.min_qty==Decimal('.1')

def test_precise_rounding_and_distance():
    assert money(Decimal('99.99')*Decimal('.25'))==Decimal('25.00')
    assert distance(11.341,77.7172,11.341,77.7172)==0
    assert 1<distance(11.341,77.7172,11.347,77.699)<3

def test_origin_guard_and_unauthenticated_access():
    client=TestClient(app)
    assert client.get('/api/v1/auth/me').status_code==401
    session=client.get('/api/v1/auth/session')
    assert session.status_code==200 and session.json()=={'user':None,'csrf':''}
    response=client.post('/api/v1/auth/login',json={'email':'a@example.com','password':'test'},headers={'Origin':'https://untrusted.example'})
    assert response.status_code==403

def test_openapi_has_core_contracts():
    paths=app.openapi()['paths']
    for route in ('/api/v1/sales','/api/v1/orders','/api/v1/checkout/branches','/api/v1/stock-counts','/api/v1/transfers','/api/v1/shifts/open'):
        assert 'post' in paths[route]
    order=OrderIn(items=[{'variant_id':1,'quantity':'2'}],method='pickup',latitude=11.341,longitude=77.7172,branch_id=1,phone='9876543210',expected_subtotal='156.00')
    assert order.expected_subtotal==Decimal('156.00')
