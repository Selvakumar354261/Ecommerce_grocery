from decimal import Decimal
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.schemas import BranchIn
from app.services import distance_delivery_fee
from conftest import login
from test_saved_addresses import customer

def branch_data():
    return {'name':'Test branch','address':'Complete branch address','latitude':11.341,'longitude':77.7172,
        'radius_km':'20','delivery_fee':'99','hours':'09:00–21:00',
        'delivery_slabs':[{'up_to_km':'10','fee':'30'},{'up_to_km':'20','fee':'60'}]}

def test_distance_slab_boundaries_and_validation():
    data=BranchIn.model_validate(branch_data())
    branch=SimpleNamespace(radius_km=data.radius_km,delivery_fee=data.delivery_fee,delivery_slabs=data.model_dump(mode='json')['delivery_slabs'])
    for km,fee in [('0','30'),('10','30'),('10.001','60'),('20','60'),('20.001','0')]:
        assert distance_delivery_fee(branch,Decimal(km))==Decimal(fee)
    for slabs in [ [{'up_to_km':'20','fee':'30'},{'up_to_km':'10','fee':'60'}],
                   [{'up_to_km':'10','fee':'30'}],
                   [{'up_to_km':'0','fee':'30'}],
                   [{'up_to_km':'20','fee':'-1'}] ]:
        with pytest.raises(ValidationError):BranchIn.model_validate({**branch_data(),'delivery_slabs':slabs})
    branch.delivery_slabs=[]
    assert distance_delivery_fee(branch,5)==Decimal('99')

def test_branch_slabs_quote_and_order_match(monkeypatch):
    admin=login('admin@gmail.com')
    response=admin.put('/api/v1/admin/branches/1',json=branch_data())
    assert response.status_code==200,response.text
    assert response.json()['delivery_slabs'][1]['fee']=='60'
    monkeypatch.setattr('app.services.distance',lambda *args:15.0)
    client=customer('9876543210')
    basket={'items':[{'variant_id':1,'quantity':'1'}],'method':'delivery','latitude':11.341,'longitude':77.7172}
    quoted=client.post('/api/v1/checkout/branches',json=basket)
    branch=next(b for b in quoted.json() if b['id']==1)
    assert Decimal(branch['delivery_fee'])==60
    placed=client.post('/api/v1/orders',json={**basket,'branch_id':1,'address':'Complete customer address','phone':'9876543210'},headers={'Idempotency-Key':'slab-order'})
    assert placed.status_code==201,placed.text
    order=client.get(f"/api/v1/orders/{placed.json()['id']}").json()
    assert Decimal(order['delivery_fee'])==60
    pickup=client.post('/api/v1/checkout/branches',json={**basket,'method':'pickup'}).json()
    assert all(Decimal(b['delivery_fee'])==0 for b in pickup)
