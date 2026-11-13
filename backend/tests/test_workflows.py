from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.db import SessionLocal
from app.main import app
from app.models import Branch, Order, OrderEvent, Product, Stock, Sale, Variant, now
from app.services import expire_reservations
from conftest import login

def stock(db,branch=1,variant=1):
    return db.scalar(select(Stock).where(Stock.branch_id==branch,Stock.variant_id==variant))

def order_body(method='pickup'):
    return {'items':[{'variant_id':1,'quantity':'2'}],'method':method,'latitude':11.341,'longitude':77.7172,'branch_id':1,'address':'Example test address','phone':'9876543210'}

def post(client,path,data,key=None):
    if path=='/sales' and 'customer_mobile' not in data:
        data={**data,'customer_mobile':'9876543210','customer_name':'Test Customer'}
    if path=='/sales' and data.get('payment_method','cash')=='cash' and 'amount_tendered' not in data:
        data={**data,'amount_tendered':'10000000.00'}
    return client.post('/api/v1'+path,json=data,headers={'Idempotency-Key':key or str(uuid4())})

def product_workbook(rows):
    headers=['product_name','category','description','tone','sku','option_label','unit','price','min_qty','step','max_qty']
    def excel_row(number,values):
        cells=[]
        for index,value in enumerate(values):
            column=chr(65+index);escaped=str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            cells.append(f'<c r="{column}{number}" t="inlineStr"><is><t>{escaped}</t></is></c>')
        return f'<row r="{number}">{"".join(cells)}</row>'
    buffer=BytesIO()
    with ZipFile(buffer,'w') as archive:
        archive.writestr('xl/workbook.xml','<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Products" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        body=''.join([excel_row(1,headers)]+[excel_row(index,row) for index,row in enumerate(rows,start=2)])
        archive.writestr('xl/worksheets/sheet1.xml',f'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>')
    return buffer.getvalue()

def test_catalogue_and_central_prices():
    client=TestClient(app);catalogue=client.get('/api/v1/catalogue').json()
    assert len(catalogue)==8
    assert len({p['id'] for p in catalogue})==len(catalogue)
    assert len({p['code'] for p in catalogue})==len(catalogue)
    assert catalogue[0]['code']=='PRD-000001'
    assert catalogue[0]['variants'][0]['price']=='78.00'
    assert client.patch('/api/v1/admin/variants/1/price',json={'price':'99'}).status_code==401
    admin=login();assert admin.patch('/api/v1/admin/variants/1/price',json={'price':'99'}).status_code==200
    assert client.get('/api/v1/catalogue').json()[0]['variants'][0]['price']=='99.00'

def test_admin_bulk_product_excel_import_is_validated_and_atomic():
    admin=login();cashier=login('cashier@grove.local')
    template=admin.get('/api/v1/admin/products/import-template')
    assert template.status_code==200 and template.content[:2]==b'PK'
    assert cashier.get('/api/v1/admin/products/import-template').status_code==403
    rows=[
        ['Bulk Rice','Rice','Imported rice','sage','BULK-RICE-1','1 kg sealed pack','pack','90','1','1','50'],
        ['Bulk Rice','Rice','Imported rice','sage','BULK-RICE-5','5 kg sealed bag','pack','430','1','1','20'],
        ['Bulk Oil','Oil','Imported oil','gold','BULK-OIL-1','1 litre bottle','litre','260','0.25','0.25','20'],
    ]
    imported=admin.post('/api/v1/admin/products/bulk-import',content=product_workbook(rows),headers={'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
    assert imported.status_code==200,imported.text
    assert imported.json()=={'products_created':2,'variants_created':3}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Product).where(Product.name.in_(['Bulk Rice','Bulk Oil'])))==2
        assert db.scalar(select(func.count()).select_from(Variant).where(Variant.sku.like('BULK-%')))==3
    invalid=[['Should Roll Back','Rice','','sage','BULK-NEW-1','Pack','pack','100','1','1','10'],['Broken Product','Rice','','sage','BULK-NEW-1','Pack','pack','100','1','1','10']]
    rejected=admin.post('/api/v1/admin/products/bulk-import',content=product_workbook(invalid),headers={'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
    assert rejected.status_code==422
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(Product).where(Product.name=='Should Roll Back'))==0

def test_branch_isolation_and_csrf():
    cashier=login('cashier@grove.local')
    assert cashier.get('/api/v1/inventory?branch_id=2').status_code==403
    assert cashier.get('/api/v1/admin/users').status_code==403
    assert cashier.post('/api/v1/sales',json={'branch_id':1,'items':[{'variant_id':1,'quantity':1}]},headers={'X-CSRF-Token':'wrong','Idempotency-Key':str(uuid4())}).status_code==403
    assert cashier.post('/api/v1/auth/register',json={'name':'New','email':'n@test.com','password':'longpassword'},headers={'Origin':'https://untrusted.example'}).status_code==403

def test_pos_barcode_scan_is_backend_validated_and_branch_scoped():
    cashier=login('cashier@grove.local')
    scanned=cashier.get('/api/v1/pos/scan?branch_id=1&code=RICE-1KG')
    assert scanned.status_code==200,scanned.text
    assert scanned.json()['variant_id']==1 and scanned.json()['sku']=='RICE-1KG' and float(scanned.json()['available'])>0
    assert scanned.json()['requires_quantity'] is False
    loose=cashier.get('/api/v1/pos/scan?branch_id=1&code=RICE-LOOSE')
    assert loose.status_code==200 and loose.json()['unit']=='kg' and loose.json()['requires_quantity'] is True
    assert cashier.get('/api/v1/pos/scan?branch_id=1&code=UNKNOWN-CODE').status_code==404
    assert cashier.get('/api/v1/pos/scan?branch_id=2&code=RICE-1KG').status_code==403
    inventory=login('inventory@grove.local')
    assert inventory.get('/api/v1/pos/scan?branch_id=1&code=RICE-1KG').status_code==403
    labels=inventory.get('/api/v1/inventory/barcode-sheet')
    assert labels.status_code==200 and 'CHINNU barcode labels' in labels.text and 'RICE-1KG' in labels.text and '<svg' in labels.text
    assert cashier.get('/api/v1/inventory/barcode-sheet').status_code==403

def test_customer_mobile_otp_login_with_optional_email():
    client=TestClient(app)
    requested=client.post('/api/v1/auth/otp/request',json={'phone':'9876543210'})
    assert requested.status_code==200 and requested.json()['development_otp']
    profile=client.post('/api/v1/auth/otp/verify',json={'phone':'9876543210','otp':requested.json()['development_otp']})
    assert profile.status_code==200 and profile.json()=={'profile_required':True}
    verified=client.post('/api/v1/auth/otp/verify',json={'phone':'9876543210','otp':requested.json()['development_otp'],'name':'Rural Customer'})
    assert verified.status_code==200,verified.text
    assert verified.json()['user']['phone']=='9876543210' and verified.json()['user']['email'] is None
    client.headers['X-CSRF-Token']=verified.json()['csrf']
    alternate=order_body('delivery');alternate['phone']='9123456789'
    created=post(client,'/orders',alternate)
    assert created.status_code==201,created.text
    defaults=client.get('/api/v1/checkout/defaults')
    assert defaults.json()=={'phone':'9876543210','address':'Example test address'}
    client.post('/api/v1/auth/logout',headers={'X-CSRF-Token':verified.json()['csrf']})
    requested=client.post('/api/v1/auth/otp/request',json={'phone':'9876543210'})
    returning=client.post('/api/v1/auth/otp/verify',json={'phone':'9876543210','otp':requested.json()['development_otp']})
    assert returning.status_code==200 and returning.json()['user']['name']=='RURAL CUSTOMER'

def test_backend_issues_role_access_capabilities():
    expected={
        'admin@grove.local':{'dashboard','inventory','users','customers','settings','audit'},
        'manager@grove.local':{'dashboard','pos','inventory','counts','sales'},
        'cashier@grove.local':{'pos','shifts','inventory','sales'},
        'inventory@grove.local':{'inventory','counts','transfers','purchases'},
        'customer@grove.local':set(),
    }
    for email,pages in expected.items():
        session=login(email)
        user=session.get('/api/v1/auth/me').json()['user']
        assert pages.issubset(set(user['workspace_pages']))
        assert ('workspace' in user['permissions']) == (email!='customer@grove.local')
        if email=='admin@grove.local':
            assert 'pos' not in user['workspace_pages']
            people=session.get('/api/v1/admin/users')
            assert people.status_code==200 and all(person['role']!='customer' for person in people.json())

    cashier=login('cashier@grove.local')
    assert cashier.get('/api/v1/dashboard').status_code==403
    assert cashier.get('/api/v1/orders').status_code==403

def test_people_directory_branch_filter():
    admin=login('admin@gmail.com')
    everyone=admin.get('/api/v1/admin/users').json()
    for branch_id in (1,2):
        response=admin.get('/api/v1/admin/users',params={'branch_id':branch_id})
        assert response.status_code==200
        assert response.json()==[u for u in everyone if u['branch_id']==branch_id]
    assert admin.get('/api/v1/admin/users',params={'branch_id':0}).status_code==422
    assert admin.get('/api/v1/admin/users',params={'branch_id':999999}).status_code==404
    manager=login('manager@gmail.com')
    assert manager.get('/api/v1/admin/users',params={'branch_id':1}).status_code==403

def test_pos_scanning_requires_cashiers_own_open_shift():
    cashier=login('cashier@gmail.com')
    assert cashier.get('/api/v1/pos/scan',params={'branch_id':1,'code':'RICE-1KG'}).status_code==200
    from app.models import Shift
    with SessionLocal.begin() as db:
        for shift in db.scalars(select(Shift).where(Shift.closed_at==None)).all():
            shift.closed_at=now()
    response=cashier.get('/api/v1/pos/scan',params={'branch_id':1,'code':'RICE-1KG'})
    assert response.status_code==409
    assert 'Open your cashier shift' in response.json()['detail']

def test_split_exact_cash_without_tender():
    admin=login('admin@gmail.com')
    body={'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'payment_method':'split','payments':[{'method':'cash','amount':'50'},{'method':'upi','amount':'28'}]}
    result=post(admin,'/sales',body)
    assert result.status_code==201,result.text
    with SessionLocal() as db:
        saved=db.get(Sale,result.json()['id'])
        assert saved.amount_tendered==Decimal('50.00')
        assert saved.change_due==0
    from app.order_payments import settlement_quote
    from app.schemas import OrderPaymentIn
    from types import SimpleNamespace
    quote=settlement_quote(SimpleNamespace(total=Decimal('78')),OrderPaymentIn.model_validate({'payment_method':'split','payments':body['payments']}))
    assert quote['amount_tendered']=='50.00' and quote['change_due']=='0.00'

def test_admin_can_edit_product_details():
    admin=login('admin@gmail.com')
    before=admin.get('/api/v1/catalogue').json()[0]
    details={'name':'Updated rice','category':'Grains','description':'Updated description','tone':'gold'}
    details['variants']=[{k:v[k] for k in ('id','sku','label','unit','price','min_qty','step','max_qty')} for v in before['variants']]
    details['variants'][0].update(label='Updated pack',price='90.00',sku='UPDATED-RICE')
    response=admin.put(f"/api/v1/admin/products/{before['id']}",json=details)
    assert response.status_code==200
    after=next(p for p in admin.get('/api/v1/catalogue').json() if p['id']==before['id'])
    assert all(after[k]==v for k,v in details.items() if k!='variants')
    assert after['variants'][0]['id']==before['variants'][0]['id']
    assert after['variants'][0]['label']=='Updated pack'
    assert after['variants'][0]['sku']=='UPDATED-RICE'
    assert Decimal(after['variants'][0]['price'])==Decimal('90.00')
    categories=admin.get('/api/v1/admin/product-categories')
    assert categories.status_code==200
    assert 'Grains' in categories.json()
    assert categories.json()==sorted(set(categories.json()))
    unsafe={**details,'variants':[{**v,'unit':'kg'} for v in details['variants']]}
    assert admin.put(f"/api/v1/admin/products/{before['id']}",json=unsafe).status_code==422
    assert admin.put(f"/api/v1/admin/products/{before['id']}",json={**details,'name':'x'}).status_code==422
    manager=login('manager@gmail.com')
    assert manager.put(f"/api/v1/admin/products/{before['id']}",json=details).status_code==403

def test_admin_can_update_staff_credentials_and_password():
    admin=login()
    previous_session=login('cashier@grove.local')
    staff=next(x for x in admin.get('/api/v1/admin/users').json() if x['role']=='cashier')
    updated=admin.put(f"/api/v1/admin/users/{staff['id']}",json={'name':'Updated Cashier','email':'updated.cashier@chinnu.local','password':'NewSecurePass!2026','role':'cashier','branch_id':2})
    assert updated.status_code==200,updated.text
    assert updated.json()['name']=='Updated Cashier' and updated.json()['email']=='updated.cashier@chinnu.local' and updated.json()['branch_id']==2
    assert previous_session.get('/api/v1/auth/me').status_code==401
    old_credentials=TestClient(app).post('/api/v1/auth/login',json={'email':'cashier@grove.local','password':'DemoGrocery!2026'})
    assert old_credentials.status_code==401
    new_session=TestClient(app)
    signed_in=new_session.post('/api/v1/auth/login',json={'email':'updated.cashier@chinnu.local','password':'NewSecurePass!2026'})
    assert signed_in.status_code==200 and signed_in.json()['user']['branch_id']==2
    duplicate=admin.put(f"/api/v1/admin/users/{staff['id']}",json={'name':'Updated Cashier','email':'manager@grove.local','password':None,'role':'cashier','branch_id':2})
    assert duplicate.status_code==409

def test_admin_can_change_own_password_and_keep_current_session():
    admin=login()
    wrong=admin.put('/api/v1/admin/password',json={'current_password':'wrong','new_password':'NewAdminPass!2026'})
    assert wrong.status_code==422
    same=admin.put('/api/v1/admin/password',json={'current_password':'DemoGrocery!2026','new_password':'DemoGrocery!2026'})
    assert same.status_code==422
    changed=admin.put('/api/v1/admin/password',json={'current_password':'DemoGrocery!2026','new_password':'NewAdminPass!2026'})
    assert changed.status_code==200,changed.text
    assert admin.get('/api/v1/auth/me').status_code==200
    assert TestClient(app).post('/api/v1/auth/login',json={'email':'admin@grove.local','password':'DemoGrocery!2026'}).status_code==401
    assert TestClient(app).post('/api/v1/auth/login',json={'email':'admin@grove.local','password':'NewAdminPass!2026'}).status_code==200
    manager=login('manager@grove.local')
    assert manager.put('/api/v1/admin/password',json={'current_password':'DemoGrocery!2026','new_password':'ManagerPass!2026'}).status_code==403

def test_checkout_recommends_nearest_full_cart():
    body=order_body();body.pop('branch_id');body.pop('address');body.pop('phone')
    result=TestClient(app).post('/api/v1/checkout/branches',json=body)
    assert result.status_code==200,result.text
    opts=result.json();assert opts[0]['id']==1 and opts[0]['recommended'] and opts[0]['eligible']
    body['items']=[{'variant_id':8,'quantity':1}]
    opts=TestClient(app).post('/api/v1/checkout/branches',json=body).json()
    assert any(not b['eligible'] for b in opts)

def test_final_order_revalidates_branch_availability_on_backend():
    customer=login('customer@grove.local')
    body=order_body()
    discovery={k:v for k,v in body.items() if k not in ('branch_id','address','phone')}
    options=customer.post('/api/v1/checkout/branches',json=discovery).json()
    assert any(x['id']==1 and x['eligible'] for x in options)
    with SessionLocal.begin() as db:
        db.get(Branch,1).accepting_orders=False
    rejected=post(customer,'/orders',body)
    assert rejected.status_code==409
    assert 'not accepting orders' in rejected.json()['detail']
    with SessionLocal() as db:
        assert stock(db).reserved==0

def test_outside_coverage_order_requires_manager_approval():
    customer=login('customer@grove.local')
    body=order_body('delivery')
    body['latitude']=0
    body['longitude']=0
    discovery={k:v for k,v in body.items() if k not in ('branch_id','address','phone')}
    option=next(x for x in customer.post('/api/v1/checkout/branches',json=discovery).json() if x['id']==1)
    assert option['eligible'] and option['requires_approval'] and not option['covered']
    placed=post(customer,'/orders',body);assert placed.status_code==201,placed.text
    assert placed.json()['status']=='approval_pending' and placed.json()['requires_approval']
    ident=placed.json()['id']
    visible=customer.get(f'/api/v1/orders/{ident}').json()
    assert visible['approval_expires_at'] and visible['coverage_approval_required']
    assert visible['delivery_fee']=='0.00' and visible['total']==visible['subtotal']
    approval={'action':'approve_coverage','delivery_charge':'180.00','estimated_delivery_days':3}
    cashier=login('cashier@grove.local')
    assert post(cashier,f'/orders/{ident}/transition',approval).status_code==403
    manager=login('manager@grove.local')
    assert post(manager,f'/orders/{ident}/transition',{'action':'approve_coverage'}).status_code==422
    approved=post(manager,f'/orders/{ident}/transition',approval)
    assert approved.status_code==200 and approved.json()['status']=='placed'
    with SessionLocal() as db:
        order=db.get(Order,ident)
        assert order.coverage_approved_by is not None and order.expires_at is not None and order.approval_expires_at is None
        assert order.delivery_fee==Decimal('180.00') and order.total==order.subtotal+Decimal('180.00') and order.estimated_delivery_days==3

def test_outside_coverage_rejection_requires_reason_and_expiry_uses_customer_message():
    customer=login('customer@grove.local');manager=login('manager@grove.local')
    body=order_body('delivery');body['latitude']=0;body['longitude']=0
    ident=post(customer,'/orders',body).json()['id']
    missing=post(manager,f'/orders/{ident}/transition',{'action':'reject_coverage'})
    assert missing.status_code==422
    reason='The delivery address cannot be served safely by this branch.'
    rejected=post(manager,f'/orders/{ident}/transition',{'action':'reject_coverage','note':reason})
    assert rejected.status_code==200 and rejected.json()['status']=='cancelled'
    visible=customer.get(f'/api/v1/orders/{ident}').json()
    assert visible['events'][-1]['note']==reason
    staff_visible=manager.get(f'/api/v1/orders/{ident}').json()
    assert staff_visible['display_status']=='rejected'

    automatic=post(customer,'/orders',body).json()['id']
    with SessionLocal.begin() as db:db.get(Order,automatic).approval_expires_at=now()-timedelta(seconds=1)
    with SessionLocal.begin() as db:assert expire_reservations(db)==1
    visible=customer.get(f'/api/v1/orders/{automatic}').json()
    assert visible['status']=='rejected'
    assert visible['events'][-1]['note']=='We were unable to confirm your order due to operational or technical reasons. Please contact the branch for assistance or place a new order.'

def test_store_rejects_normal_order_with_customer_visible_reason():
    customer=login('customer@grove.local');manager=login('manager@grove.local')
    ident=post(customer,'/orders',order_body()).json()['id']
    assert post(manager,f'/orders/{ident}/transition',{'action':'reject'}).status_code==422
    assert post(manager,f'/orders/{ident}/transition',{'action':'cancel','note':'Store cancellation'}).status_code==422
    reason='The requested items are currently unavailable at this branch.'
    rejected=post(manager,f'/orders/{ident}/transition',{'action':'reject','note':reason})
    assert rejected.status_code==200 and rejected.json()['status']=='cancelled'
    visible=customer.get(f'/api/v1/orders/{ident}').json()
    assert visible['status']=='rejected' and visible['display_status']=='rejected'
    assert visible['events'][-1]['status']=='rejected' and visible['events'][-1]['note']==reason

def test_legacy_staff_cancellation_is_displayed_as_rejected():
    customer=login('customer@grove.local');manager=login('manager@grove.local')
    ident=post(customer,'/orders',order_body()).json()['id']
    manager_id=manager.get('/api/v1/auth/me').json()['user']['id']
    with SessionLocal.begin() as db:
        order=db.get(Order,ident);order.status='cancelled';order.reserved_active=False
        db.add(OrderEvent(order_id=ident,status='cancelled',actor_id=manager_id,note='Requested stock is unavailable.'))
    visible=manager.get(f'/api/v1/orders/{ident}').json()
    assert visible['status']=='cancelled' and visible['display_status']=='rejected'
    assert customer.get(f'/api/v1/orders/{ident}').json()['status']=='rejected'

def test_idempotent_pos_and_stock_deduction():
    admin=login();body={'branch_id':1,'items':[{'variant_id':1,'quantity':'2'}]};key='sale-once'
    a=post(admin,'/sales',body,key);b=post(admin,'/sales',body,key)
    assert a.status_code==201,a.text
    assert a.json()==b.json()
    with SessionLocal() as db:
        assert stock(db).on_hand==38
        assert db.scalar(select(func.count(Sale.id)))==1
    body['items'][0]['quantity']='3'
    assert post(admin,'/sales',body,key).status_code==409

def test_reserve_cancel_and_expiry_release_once():
    customer=login('customer@grove.local')
    r=post(customer,'/orders',order_body());assert r.status_code==201,r.text
    ident=r.json()['id']
    with SessionLocal() as db:assert stock(db).reserved==2
    key='cancel-once'
    assert post(customer,f'/orders/{ident}/transition',{'action':'cancel'},key).status_code==200
    assert post(customer,f'/orders/{ident}/transition',{'action':'cancel'},key).status_code==200
    with SessionLocal() as db:assert stock(db).on_hand==40 and stock(db).reserved==0
    ident=post(customer,'/orders',order_body()).json()['id']
    with SessionLocal.begin() as db:db.get(Order,ident).expires_at=now()-timedelta(seconds=1)
    with SessionLocal.begin() as db:assert expire_reservations(db)==1
    with SessionLocal.begin() as db:assert expire_reservations(db)==0
    with SessionLocal() as db:assert stock(db).reserved==0

def test_admin_configures_reservation_duration_used_by_backend():
    admin=login();manager=login('manager@grove.local')
    assert manager.get('/api/v1/admin/settings/reservations').status_code==403
    changed=admin.put('/api/v1/admin/settings/reservations',json={'reservation_hours':6})
    assert changed.status_code==200 and changed.json()['reservation_hours']==6
    assert admin.put('/api/v1/admin/settings/reservations',json={'reservation_hours':0}).status_code==422
    customer=login('customer@grove.local')
    created=post(customer,'/orders',order_body());assert created.status_code==201,created.text
    with SessionLocal() as db:
        remaining=(db.get(Order,created.json()['id']).expires_at-now()).total_seconds()/3600
        assert 5.99<=remaining<=6

def test_pickup_completion_consumes_reservation_once():
    customer=login('customer@grove.local');admin=login()
    ident=post(customer,'/orders',order_body()).json()['id']
    for action in ['confirm','prepare','ready']:
        r=post(admin,f'/orders/{ident}/transition',{'action':action});assert r.status_code==200,r.text
    assert post(admin,f'/orders/{ident}/transition',{'action':'collect','pickup_code':'000000'}).status_code==422
    assert admin.post(f'/api/v1/orders/{ident}/payment',json={'payment_method':'cash','amount_tendered':'200.00'}).status_code==200
    code=customer.get(f'/api/v1/orders/{ident}').json()['pickup_code']
    r=post(admin,f'/orders/{ident}/transition',{'action':'collect','pickup_code':code},'collect-once');assert r.status_code==200,r.text
    assert post(admin,f'/orders/{ident}/transition',{'action':'collect','pickup_code':code},'collect-once').status_code==200
    online_sales=admin.get('/api/v1/online-sales?branch_id=1')
    assert online_sales.status_code==200 and online_sales.json()[0]['id']==ident
    with SessionLocal() as db:assert stock(db).on_hand==38 and stock(db).reserved==0

def test_delivery_mobile_assignment_cash_otp_and_role_isolation():
    admin=login();manager=login('manager@grove.local');customer=login('customer@grove.local')
    created=admin.post('/api/v1/admin/users',json={'name':'Branch Driver','email':'driver@chinnu.local','password':'DriverPass!2026','role':'delivery','branch_id':1})
    assert created.status_code==200,created.text
    driver_id=created.json()['id']
    ident=post(customer,'/orders',order_body('delivery')).json()['id']
    for action in ['confirm','prepare','ready']:
        result=post(manager,f'/orders/{ident}/transition',{'action':action})
        assert result.status_code==200,result.text
    assigned=admin.post(f'/api/v1/orders/{ident}/assign-delivery',json={'delivery_user_id':driver_id})
    assert assigned.status_code==200 and assigned.json()['assigned_delivery_user_id']==driver_id
    customer_assignment=customer.get(f'/api/v1/orders/{ident}').json()
    assert customer_assignment['assigned_delivery_name'] is None
    assignment_event=next(event for event in customer_assignment['events'] if event['status']=='delivery_assigned')
    assert assignment_event['display_status']=='dispatched' and assignment_event['note']==''
    assert assigned.json()['events'][-1]['note']=='Assigned to Branch Driver.'
    signed_in=TestClient(app).post('/api/v1/delivery/auth/login',json={'email':'driver@chinnu.local','password':'DriverPass!2026'})
    assert signed_in.status_code==200,signed_in.text
    mobile=TestClient(app,headers={'Authorization':f"Bearer {signed_in.json()['token']}"})
    jobs=mobile.get('/api/v1/delivery/orders')
    assert jobs.status_code==200 and jobs.json()[0]['id']==ident and 'pickup_code' not in jobs.json()[0]
    assert jobs.json()[0]['latitude']=='11.3410000' and jobs.json()[0]['longitude']=='77.7172000'
    assert mobile.get('/api/v1/inventory?branch_id=1').status_code==403
    assert mobile.get('/api/v1/orders').status_code==403
    started=mobile.post(f'/api/v1/delivery/orders/{ident}/start',headers={'Idempotency-Key':'driver-start'})
    assert started.status_code==200 and started.json()['status']=='dispatched'
    customer_trip=customer.get(f'/api/v1/orders/{ident}').json()
    assert customer_trip['events'][-1]['note']=='Delivery person started the trip.'
    assert customer_trip['events'][-1]['display_status']=='delivery_started'
    location=mobile.post(f'/api/v1/delivery/orders/{ident}/location',json={'latitude':11.3421,'longitude':77.7183})
    assert location.status_code==200
    assert customer.get(f'/api/v1/orders/{ident}/tracking').status_code==403
    tracking=manager.get(f'/api/v1/orders/{ident}/tracking')
    assert tracking.status_code==200 and tracking.json()['driver_latitude']=='11.3421000' and tracking.json()['driver_name']=='Branch Driver'
    failed=mobile.post(f'/api/v1/delivery/orders/{ident}/failed',json={'reason':'Customer requested a later delivery attempt.'})
    assert failed.status_code==200
    assert mobile.post(f'/api/v1/delivery/orders/{ident}/complete',json={'otp':'000000'},headers={'Idempotency-Key':'wrong-otp'}).status_code==422
    assert mobile.post(f'/api/v1/orders/{ident}/payment',json={'payment_method':'cash','amount_tendered':'200.00'}).status_code==200
    code=customer.get(f'/api/v1/orders/{ident}').json()['pickup_code']
    completed=mobile.post(f'/api/v1/delivery/orders/{ident}/complete',json={'otp':code},headers={'Idempotency-Key':'complete-delivery'})
    assert completed.status_code==200 and completed.json()['status']=='completed'
    customer_history=customer.get(f'/api/v1/orders/{ident}').json()['events']
    assert customer_history[-1]['tone']=='success'
    assert next(event for event in customer_history if event['status']=='payment_received')['tone']=='success'
    assert next(event for event in customer_history if event['status']=='delivery_failed')['tone']=='error'
    assert mobile.get('/api/v1/delivery/orders').json()==[]
    with SessionLocal() as db:
        order=db.get(Order,ident)
        assert order.status=='completed' and stock(db).on_hand==38 and stock(db).reserved==0
        assert db.scalar(select(func.count(OrderEvent.id)).where(OrderEvent.order_id==ident,OrderEvent.status=='delivery_failed'))==1

def test_oversell_concurrency_between_pos_and_order():
    with SessionLocal.begin() as db:stock(db).on_hand=1
    admin=login();customer=login('customer@grove.local')
    body=order_body();body['items'][0]['quantity']='1'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda fn:fn(),[lambda:post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}]}),lambda:post(customer,'/orders',body)]))
    assert sorted(r.status_code for r in results)==[201,409],[r.text for r in results]
    with SessionLocal() as db:
        s=stock(db);assert s.on_hand-s.reserved-s.damaged==0

def test_transfer_partial_receipt():
    admin=login();r=post(admin,'/transfers',{'source_id':1,'target_id':2,'variant_id':1,'quantity':'10'});assert r.status_code==200,r.text
    ident=r.json()['id']
    assert post(admin,f'/transfers/{ident}/receive',{'quantity':'8'}).status_code==200
    with SessionLocal() as db:assert stock(db).on_hand==30 and stock(db,2).on_hand==58
    assert post(admin,f'/transfers/{ident}/receive',{'quantity':'3'}).status_code==409

def test_reserved_stock_cannot_be_damaged_or_sold():
    customer=login('customer@grove.local');admin=login()
    with SessionLocal.begin() as db:stock(db).on_hand=2
    assert post(customer,'/orders',order_body()).status_code==201
    assert post(admin,'/inventory/change',{'branch_id':1,'variant_id':1,'quantity':1,'kind':'damage','reason':'Damaged during count'}).status_code==409
    assert post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':1}]}).status_code==409

def test_returns_and_snapshot_prices():
    admin=login();r=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'2'}]});assert r.status_code==201
    sale=admin.get('/api/v1/sales?branch_id=1').json()[0]
    assert admin.patch('/api/v1/admin/variants/1/price',json={'price':'100'}).status_code==200
    assert sale['total']=='156.00'
    result=post(admin,f"/sales/{sale['id']}/returns",{'item_id':sale['items'][0]['id'],'quantity':'2','condition':'damaged','reason':'Packaging damaged'},'return-once')
    assert result.status_code==200,result.text
    assert result.json()['refund']=='156.00'
    with SessionLocal() as db:assert stock(db).on_hand==40 and stock(db).damaged==2

def test_purchases_do_not_change_stock_until_receipt():
    admin=login();p=post(admin,'/purchases',{'supplier_id':1,'branch_id':1,'variant_id':1,'quantity':'5','unit_cost':'60'})
    assert p.status_code==200,p.text
    with SessionLocal() as db:assert stock(db).on_hand==40
    assert post(admin,f"/purchases/{p.json()['id']}/receive",{'quantity':'5','unit_cost':'62'}).status_code==200
    with SessionLocal() as db:assert stock(db).on_hand==45
    purchase=admin.get('/api/v1/purchases').json()[0]
    assert purchase['unit_cost']=='62.00'
    assert purchase['selling_price']=='78.00'
    assert purchase['profit_per_unit']=='16.00'

def test_quantity_rules_and_customer_order_privacy():
    admin=login();customer=login('customer@grove.local')
    assert post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'.5'}]}).status_code==422
    ident=post(customer,'/orders',order_body()).json()['id']
    other=TestClient(app);r=other.post('/api/v1/auth/register',json={'name':'Other Customer','email':'other@example.com','password':'OtherLongPassword'})
    assert r.status_code==201,r.text
    assert other.get(f'/api/v1/orders/{ident}').status_code==404

def test_shift_close_and_count_approval():
    admin=login();cashier=login('cashier@grove.local');manager=login('manager@grove.local');inventory=login('inventory@grove.local')
    shifts=cashier.get('/api/v1/shifts?branch_id=1').json()
    assert len(shifts)==1
    assert shifts[0]['client_ip'] and shifts[0]['system_info']
    assert 'IP ' in shifts[0]['cashier']
    assert post(cashier,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}]}).status_code==201
    missing=post(cashier,f"/shifts/{shifts[0]['id']}/close",{'branch_id':1,'cash':'70','card':'0','upi':'0'})
    assert missing.status_code==422
    result=post(cashier,f"/shifts/{shifts[0]['id']}/close",{'branch_id':1,'cash':'70','card':'0','upi':'0','shortage_reason':'Cash drawer was short during physical count'})
    assert result.status_code==200,result.text
    assert result.json()['variance']=='-8.00' and result.json()['closure_status']=='pending'
    assert result.json()['card_variance']=='0.00'
    assert result.json()['upi_variance']=='0.00'
    assert post(cashier,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}]}).status_code==409
    approval=post(manager,f"/shifts/{shifts[0]['id']}/approve-close",{})
    assert approval.status_code==200 and approval.json()['closure_status']=='approved'
    request=post(inventory,'/stock-counts',{'branch_id':1,'variant_id':1,'counted_quantity':'38','reason':'Physical shelf count'})
    assert request.status_code==200,request.text
    ident=request.json()['id']
    assert post(inventory,f'/stock-counts/{ident}/approve',{}).status_code==403
    assert post(admin,f'/stock-counts/{ident}/approve',{}).status_code==200
    with SessionLocal() as db:assert stock(db).on_hand==38

def test_pos_payment_methods_and_cash_change():
    admin=login('cashier@grove.local');manager=login('manager@grove.local')
    cash=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'payment_method':'cash','amount_tendered':'100'})
    assert cash.status_code==201,cash.text
    assert cash.json()['change_due']=='22.00'
    card=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'payment_method':'card'})
    assert card.status_code==201,card.text
    upi=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'payment_method':'upi'})
    assert upi.status_code==201,upi.text
    split=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'payment_method':'split','payments':[{'method':'cash','amount':'50'},{'method':'card','amount':'28'}]})
    assert split.status_code==201,split.text
    assert split.json()['change_due']=='0.00' and split.json()['payment_method']=='split'
    assert {part['method']:part['amount'] for part in split.json()['payments']}=={'cash':'50.00','card':'28.00'}
    invalid_split=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'payment_method':'split','payments':[{'method':'cash','amount':'50'},{'method':'upi','amount':'20'}],'amount_tendered':'50'})
    assert invalid_split.status_code==422
    short=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'payment_method':'cash','amount_tendered':'50'})
    assert short.status_code==422
    shift=admin.get('/api/v1/shifts?branch_id=1').json()[0]
    assert shift['current_expected']=='128.00'
    assert shift['current_expected_card']=='106.00'
    assert shift['current_expected_upi']=='78.00'
    closed=post(admin,f"/shifts/{shift['id']}/close",{'branch_id':1,'cash':'128','card':'106','upi':'78'})
    assert closed.status_code==200,closed.text
    assert closed.json()['closure_status']=='pending'
    assert closed.json()['variance']=='0.00'
    assert closed.json()['card_variance']=='0.00'
    assert closed.json()['upi_variance']=='0.00'
    assert post(manager,f"/shifts/{shift['id']}/approve-close",{}).status_code==200

def test_pos_customer_name_is_reused_by_mobile_number():
    admin=login()
    first=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'customer_mobile':'9123456789','customer_name':'Anita Kumar'})
    assert first.status_code==201,first.text
    lookup=admin.get('/api/v1/pos-customers/lookup?mobile=9123456789')
    assert lookup.status_code==200 and lookup.json()['name']=='ANITA KUMAR'
    assert lookup.json()['customer_code'].startswith('CUS-')
    second=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'customer_mobile':'9123456789'})
    assert second.status_code==201,second.text
    sales=admin.get('/api/v1/sales?branch_id=1').json()
    assert sales[0]['customer_name']=='ANITA KUMAR' and sales[0]['customer_mobile']=='9123456789'
    assert sales[0]['customer_code']==lookup.json()['customer_code']
    missing=admin.get('/api/v1/pos-customers/lookup?mobile=9234567890')
    assert missing.status_code==200 and missing.json()['found'] is False

    directory=admin.get('/api/v1/admin/customers?q=Anita')
    assert directory.status_code==200 and len(directory.json())==1
    customer=directory.json()[0]
    assert customer['mobile']=='9123456789' and customer['visits']==2
    assert customer['lifetime_value']=='156.00' and customer['preferred_payment']=='cash'
    detail=admin.get(f"/api/v1/admin/customers/{customer['id']}")
    assert detail.status_code==200 and len(detail.json()['sales'])==2
    assert login('manager@grove.local').get('/api/v1/admin/customers').status_code==403

def test_customer_directory_links_online_and_store_history_by_mobile():
    customer=login('customer@grove.local')
    admin=login()
    online_only=admin.get('/api/v1/admin/customers?q=9876543210')
    assert online_only.status_code==200 and len(online_only.json())==1
    assert online_only.json()[0]['source']=='online'
    sold=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'1'}],'customer_mobile':'9876543210','customer_name':'Different Store Name'})
    assert sold.status_code==201,sold.text
    placed=post(customer,'/orders',order_body())
    assert placed.status_code==201,placed.text
    linked=admin.get('/api/v1/admin/customers?q=9876543210').json()
    assert len(linked)==1 and linked[0]['source']=='linked'
    assert linked[0]['name']=='DEMO CUSTOMER'
    assert linked[0]['pos_purchases']==1 and linked[0]['online_orders']==1
    detail=admin.get('/api/v1/admin/customers/9876543210')
    assert detail.status_code==200,detail.text
    assert detail.json()['sales'][0]['customer_name']=='DEMO CUSTOMER'
    assert len(detail.json()['sales'])==1 and len(detail.json()['orders'])==1

def test_receipt_search_and_multi_item_exchange_are_atomic():
    admin=login()
    sold=post(admin,'/sales',{'branch_id':1,'items':[{'variant_id':1,'quantity':'2'}],'customer_mobile':'9345678901','customer_name':'Return Customer'})
    assert sold.status_code==201,sold.text
    receipt=f"POS-{sold.json()['id']:06d}"
    by_receipt=admin.get(f'/api/v1/return-sales?branch_id=1&q={receipt}').json()
    by_mobile=admin.get('/api/v1/return-sales?branch_id=1&q=9345678901').json()
    assert len(by_receipt)==1 and by_mobile[0]['id']==sold.json()['id']
    line=by_receipt[0]['items'][0]
    exchange=post(admin,f"/sales/{sold.json()['id']}/return-exchange",{'returns':[{'item_id':line['id'],'quantity':'1','condition':'sellable'}],'replacements':[{'variant_id':10,'quantity':'1'},{'variant_id':11,'quantity':'1'}],'settlement_method':'upi','reason':'Customer requested different products'})
    assert exchange.status_code==200,exchange.text
    body=exchange.json()
    assert body['original_receipt']==receipt and body['number'].startswith('EXC-')
    assert body['return_total']=='78.00' and body['replacement_total']=='227.00'
    assert body['amount_due']=='149.00' and body['refund_due']=='0.00'
    refreshed=admin.get(f'/api/v1/return-sales?branch_id=1&q={receipt}').json()[0]
    assert refreshed['items'][0]['returned']=='1.000'
    remaining=refreshed['items'][0]
    cash_body={'returns':[{'item_id':remaining['id'],'quantity':'1','condition':'sellable'}],'replacements':[{'variant_id':10,'quantity':'1'}],'settlement_method':'cash','reason':'Second exchange with cash balance'}
    quote=admin.post(f"/api/v1/sales/{sold.json()['id']}/return-exchange/quote",json=cash_body)
    assert quote.status_code==200 and quote.json()['amount_due']=='87.00'
    short=post(admin,f"/sales/{sold.json()['id']}/return-exchange",{**cash_body,'amount_tendered':'80'})
    assert short.status_code==422
    paid=post(admin,f"/sales/{sold.json()['id']}/return-exchange",{**cash_body,'amount_tendered':'100'})
    assert paid.status_code==200,paid.text
    assert paid.json()['amount_tendered']=='100.00' and paid.json()['change_due']=='13.00'
    saved=admin.get('/api/v1/return-exchanges?branch_id=1')
    assert saved.status_code==200,saved.text
    saved_receipt=next(x for x in saved.json() if x['id']==paid.json()['id'])
    assert saved_receipt['number']==paid.json()['number']
    assert saved_receipt['original_receipt']==receipt
    assert saved_receipt['customer_name']=='RETURN CUSTOMER'
    assert saved_receipt['returned_items'] and saved_receipt['replacement_items']
    exchanges_only=admin.get('/api/v1/return-exchanges?branch_id=1&kind=exchange')
    assert exchanges_only.status_code==200
    assert exchanges_only.json() and all(x['kind']=='exchange' for x in exchanges_only.json())
    assert admin.get('/api/v1/return-exchanges?branch_id=1&kind=invalid').status_code==422

def test_inventory_available_threshold_is_enforced_by_backend():
    admin=login()
    lower=admin.get('/api/v1/inventory?branch_id=1&threshold=39&comparison=lt')
    assert lower.status_code==200,lower.text
    assert lower.json() and all(float(item['available'])<39 for item in lower.json())
    greater=admin.get('/api/v1/inventory?branch_id=1&threshold=39&comparison=gt')
    assert greater.status_code==200,greater.text
    assert greater.json() and all(float(item['available'])>39 for item in greater.json())
    assert admin.get('/api/v1/inventory?branch_id=1&threshold=-1&comparison=lt').status_code==422
    assert admin.get('/api/v1/inventory?branch_id=1&threshold=39').status_code==422
