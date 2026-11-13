import csv
import hashlib
from html import escape
import io
import json
import logging
import os
import secrets
import urllib.request
import uuid
from datetime import date as Date, timedelta
from decimal import Decimal
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import case, delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session as DBSession
from .db import database
from .models import *
from .schemas import *
from .security import access_for, create_session, current_user, hash_password, require, scope, token_hash, verify_password
from .services import audit, available, create_order, create_sale, eligibility, get_or_404, idempotent, lines, lock_stock, money, reservation_hours, transition, stock_quantity
from .xlsx_import import product_rows
from .barcodes import code128_svg
from .delivery_reporting import operations_detail, operations_report
from .order_payments import collection_order, collection_view, record_collection, settlement_quote

app=FastAPI(title='CHINNU Commerce API',version='1.0.0',docs_url='/api/docs',openapi_url='/api/openapi.json',redoc_url=None)
prefix='/api/v1'
logger=logging.getLogger('uvicorn.error')
UserDep=Depends(current_user)
DB=Depends(database)

def row(obj,exclude=()):
    return {c.name:(str(getattr(obj,c.name)) if isinstance(getattr(obj,c.name),Decimal) else getattr(obj,c.name)) for c in obj.__table__.columns if c.name not in exclude}
def user_view(user): return {**row(user,('password_hash',)),**access_for(user)}
def product_code(product): return f'PRD-{product.id:06d}'
def system_label(user_agent):
    ua=user_agent or ''
    os_name='Windows' if 'Windows' in ua else 'Android' if 'Android' in ua else 'iPhone / iOS' if 'iPhone' in ua or 'iPad' in ua else 'macOS' if 'Mac OS' in ua else 'Linux' if 'Linux' in ua else 'Unknown OS'
    browser='Microsoft Edge' if 'Edg/' in ua else 'Chrome' if 'Chrome/' in ua else 'Firefox' if 'Firefox/' in ua else 'Safari' if 'Safari/' in ua else 'Unknown browser'
    return f'{browser} · {os_name}'

@app.middleware('http')
async def guard(request,call_next):
    request_id=str(uuid.uuid4())
    if request.method not in ('GET','HEAD','OPTIONS'):
        allowed=set(os.getenv('ALLOWED_ORIGINS','http://localhost:8080,http://127.0.0.1:8080').split(','))
        origin=request.headers.get('origin')
        if origin and origin not in allowed:
            return JSONResponse({'detail':'Request origin is not allowed.'},status_code=403)
    response=await call_next(request)
    response.headers['X-Request-ID']=request_id
    response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(IntegrityError)
async def constraint_error(request,exc):
    logger.warning('Constraint rejected operation at %s',request.url.path)
    return JSONResponse({'detail':'This operation conflicts with existing data or stock constraints.'},status_code=409)

@app.exception_handler(OperationalError)
async def operational_error(request,exc):
    logger.error('Database operation failed at %s',request.url.path)
    return JSONResponse({'detail':'The operation could not finish. Retry with the same request key.'},status_code=503)

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    errors=[f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()]
    return JSONResponse({'detail':'Please check your entries.','fields':errors},status_code=422)

@app.get(prefix+'/health')
def health(db: DBSession=DB):
    db.execute(text('SELECT 1'))
    return {'status':'ok','service':'chinnu-api'}

def set_session(db,user,response):
    token,csrf=create_session(db,user)
    response.set_cookie('grocery_session',token,max_age=43200,httponly=True,secure=os.getenv('COOKIE_SECURE','false').lower()=='true',samesite='lax',path='/')
    return {'user':user_view(user),'csrf':csrf}

def otp_digest(phone,code):
    return hashlib.sha256(f"{os.getenv('OTP_SECRET','')}:{phone}:{code}".encode()).hexdigest()

def deliver_otp(phone,code):
    mode=os.getenv('OTP_DELIVERY_MODE','development').lower()
    if mode=='development':
        logger.warning('Development OTP for %s is %s',phone,code)
        return code
    webhook=os.getenv('OTP_WEBHOOK_URL','').strip()
    if not webhook: raise HTTPException(503,'SMS delivery is not configured. Please contact the shop.')
    payload=json.dumps({'phone':phone,'otp':code,'message':f'Your CHINNU login OTP is {code}. It expires in 5 minutes.'}).encode()
    headers={'Content-Type':'application/json'}
    token=os.getenv('OTP_WEBHOOK_TOKEN','').strip()
    if token: headers['Authorization']='Bearer '+token
    try:
        with urllib.request.urlopen(urllib.request.Request(webhook,data=payload,headers=headers,method='POST'),timeout=10) as response:
            if response.status>=300: raise RuntimeError('SMS gateway rejected the request')
    except Exception:
        logger.exception('OTP delivery failed for %s',phone)
        raise HTTPException(503,'The OTP could not be sent. Please try again.')
    return None

@app.post(prefix+'/auth/otp/request')
def request_otp(data:OTPRequestIn,db:DBSession=DB):
    phone=data.phone
    lock=int.from_bytes(hashlib.sha256(('otp:'+phone).encode()).digest()[:8],'big',signed=True)
    db.execute(text('SELECT pg_advisory_xact_lock(:k)'),{'k':lock})
    record=db.get(MobileOTP,phone)
    if record and record.sent_at>now()-timedelta(seconds=60): raise HTTPException(429,'Please wait one minute before requesting another OTP.')
    code=f'{secrets.randbelow(1000000):06d}'
    if not record: record=MobileOTP(phone=phone,code_hash='',expires_at=now());db.add(record)
    record.code_hash=otp_digest(phone,code);record.expires_at=now()+timedelta(minutes=5);record.sent_at=now();record.attempts=0
    development_otp=deliver_otp(phone,code)
    return {'sent':True,'expires_in_seconds':300,**({'development_otp':development_otp} if development_otp else {})}

@app.post(prefix+'/auth/otp/verify')
def verify_otp(data:OTPVerifyIn,response:Response,db:DBSession=DB):
    record=db.get(MobileOTP,data.phone)
    if not record or record.expires_at<=now(): raise HTTPException(401,'The OTP has expired. Request a new one.')
    if record.attempts>=5: raise HTTPException(429,'Too many incorrect attempts. Request a new OTP.')
    if not secrets.compare_digest(record.code_hash,otp_digest(data.phone,data.otp)):
        record.attempts+=1;db.commit()
        raise HTTPException(401,'The OTP is incorrect.')
    user=db.scalar(select(User).where(User.phone==data.phone))
    if not user and not (data.name or '').strip():
        return {'profile_required':True}
    email=(data.email or '').strip().lower() or None
    if email and ('@' not in email or '.' not in email.split('@')[-1]): raise HTTPException(422,'Enter a valid email address or leave it blank.')
    if not user and email:
        candidate=db.scalar(select(User).where(User.email==email))
        if candidate and candidate.role=='customer' and not candidate.phone: user=candidate
        elif candidate: raise HTTPException(409,'This email address is already used by another account.')
    if not user:
        name=(data.name or '').strip().upper()
        if len(name)<2: raise HTTPException(422,'Enter the customer name for a new mobile number.')
        user=User(name=name,email=email,phone=data.phone,password_hash=None,role='customer');db.add(user);db.flush()
        audit(db,user,'account.register.mobile',user.id)
    else:
        if not user.active: raise HTTPException(401,'This account is inactive.')
        if user.role!='customer': raise HTTPException(403,'Staff must sign in with email and password.')
        if not user.phone: user.phone=data.phone
        if email and not user.email:
            if db.scalar(select(User).where(User.email==email,User.id!=user.id)): raise HTTPException(409,'This email address is already used by another account.')
            user.email=email
    user.name=user.name.strip().upper()
    store_customer=db.scalar(select(POSCustomer).where(POSCustomer.mobile==data.phone))
    if store_customer and store_customer.name!=user.name:
        store_customer.name=user.name;store_customer.updated_at=now()
    db.delete(record)
    audit(db,user,'account.login.mobile',user.id)
    return set_session(db,user,response)

@app.post(prefix+'/auth/register',status_code=201)
def register(data:RegisterIn,response:Response,db:DBSession=DB):
    email=data.email.strip().lower()
    if '@' not in email or '.' not in email.split('@')[-1]: raise HTTPException(422,'Enter a valid email address.')
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'An account with this email already exists.')
    user=User(name=data.name.strip().upper(),email=email,password_hash=hash_password(data.password),role='customer')
    db.add(user);db.flush();audit(db,user,'account.register',user.id)
    return set_session(db,user,response)

@app.post(prefix+'/auth/login')
def login(data:LoginIn,request:Request,response:Response,db:DBSession=DB):
    email=data.email.strip().lower()
    key=hashlib.sha256(f'{email}:{request.client.host if request.client else "unknown"}'.encode()).hexdigest()
    lock=int.from_bytes(bytes.fromhex(key)[:8],'big',signed=True)
    db.execute(text('SELECT pg_advisory_xact_lock(:k)'),{'k':lock})
    attempt=db.get(LoginAttempt,key)
    if not attempt: attempt=LoginAttempt(key=key,count=0,window=now());db.add(attempt)
    if attempt.window < now()-timedelta(minutes=15): attempt.count=0;attempt.window=now()
    if attempt.count>=10: raise HTTPException(429,'Too many login attempts. Try again in 15 minutes.')
    user=db.scalar(select(User).where(User.email==email))
    if not user or not user.active or not verify_password(data.password,user.password_hash):
        attempt.count+=1;db.commit()
        raise HTTPException(401,'Email or password is incorrect.')
    if user.role=='customer': raise HTTPException(403,'Customers must sign in with mobile OTP.')
    attempt.count=0
    return set_session(db,user,response)

@app.post(prefix+'/delivery/auth/login')
def delivery_login(data:LoginIn,request:Request,db:DBSession=DB):
    email=data.email.strip().lower()
    key=hashlib.sha256(f'delivery:{email}:{request.client.host if request.client else "unknown"}'.encode()).hexdigest()
    lock=int.from_bytes(bytes.fromhex(key)[:8],'big',signed=True)
    db.execute(text('SELECT pg_advisory_xact_lock(:k)'),{'k':lock})
    attempt=db.get(LoginAttempt,key)
    if not attempt:attempt=LoginAttempt(key=key,count=0,window=now());db.add(attempt)
    if attempt.window<now()-timedelta(minutes=15):attempt.count=0;attempt.window=now()
    if attempt.count>=10:raise HTTPException(429,'Too many login attempts. Try again in 15 minutes.')
    user=db.scalar(select(User).where(User.email==email))
    if not user or not user.active or user.role!='delivery' or not verify_password(data.password,user.password_hash):
        attempt.count+=1;db.commit();raise HTTPException(401,'Email or password is incorrect.')
    attempt.count=0
    token,csrf=create_session(db,user);audit(db,user,'delivery.login',user.id)
    return {'token':token,'user':user_view(user),'expires_in':43200}

@app.get(prefix+'/auth/me')
def me(request:Request,user:User=UserDep): return {'user':user_view(user),'csrf':request.state.csrf}

@app.get(prefix+'/auth/session')
def session_status(request:Request,db:DBSession=DB):
    token=request.cookies.get('grocery_session','')
    session=db.get(Session,token_hash(token)) if token else None
    if not session or session.expires_at<=now(): return {'user':None,'csrf':''}
    user=db.get(User,session.user_id)
    if not user or not user.active:return {'user':None,'csrf':''}
    return {'user':user_view(user),'csrf':session.csrf}

@app.post(prefix+'/auth/logout')
def logout(request:Request,response:Response,user:User=UserDep,db:DBSession=DB):
    session=db.get(Session,token_hash(request.cookies.get('grocery_session','')))
    if session: db.delete(session)
    response.delete_cookie('grocery_session',path='/')
    return {'ok':True}

@app.get(prefix+'/catalogue')
def catalogue(db:DBSession=DB):
    products=db.scalars(select(Product).where(Product.active==True).order_by(Product.id)).all()
    result=[]
    for product in products:
        variants=db.scalars(select(Variant).where(Variant.product_id==product.id,Variant.active==True).order_by(Variant.id)).all()
        opts=[]
        for variant in variants:
            maximum=db.scalar(select(func.max(Stock.on_hand-Stock.reserved-Stock.damaged)).join(Branch,Branch.id==Stock.branch_id).where(Stock.variant_id==variant.id,Branch.active==True,Branch.accepting_orders==True)) or 0
            opts.append({**row(variant),'available_somewhere':maximum})
        result.append({**row(product),'code':product_code(product),'variants':opts})
    return result

@app.get(prefix+'/branches')
def branches(db:DBSession=DB):
    return [row(b) for b in db.scalars(select(Branch).where(Branch.active==True).order_by(Branch.id)).all()]

@app.post(prefix+'/checkout/branches')
def checkout_branches(data:EligibilityIn,db:DBSession=DB): return eligibility(db,data)

@app.get(prefix+'/customer/addresses')
def saved_addresses(user:User=UserDep,db:DBSession=DB):
    require(user,('customer',))
    return [row(a) for a in db.scalars(select(CustomerAddress).where(CustomerAddress.user_id==user.id).order_by(CustomerAddress.id)).all()]

@app.post(prefix+'/customer/addresses',status_code=201)
def save_address(data:CustomerAddressIn,user:User=UserDep,db:DBSession=DB):
    require(user,('customer',))
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    if db.scalar(select(func.count()).select_from(CustomerAddress).where(CustomerAddress.user_id==user.id))>=20:
        raise HTTPException(422,'You can save up to 20 addresses. Remove an unused address first.')
    address=CustomerAddress(user_id=user.id,**data.model_dump());db.add(address);db.flush()
    return row(address)

@app.put(prefix+'/customer/addresses/{ident}')
def update_address(ident:int,data:CustomerAddressIn,user:User=UserDep,db:DBSession=DB):
    require(user,('customer',))
    address=db.scalar(select(CustomerAddress).where(CustomerAddress.id==ident,CustomerAddress.user_id==user.id).with_for_update())
    if not address:raise HTTPException(404,'Saved address not found.')
    for key,value in data.model_dump().items():setattr(address,key,value)
    return row(address)

@app.delete(prefix+'/customer/addresses/{ident}')
def delete_address(ident:int,user:User=UserDep,db:DBSession=DB):
    require(user,('customer',))
    address=db.scalar(select(CustomerAddress).where(CustomerAddress.id==ident,CustomerAddress.user_id==user.id).with_for_update())
    if not address:raise HTTPException(404,'Saved address not found.')
    db.delete(address)
    return {'ok':True}

@app.get(prefix+'/checkout/defaults')
def checkout_defaults(user:User=UserDep,db:DBSession=DB):
    require(user,('customer',))
    previous=db.scalar(select(Order).where(Order.user_id==user.id,Order.method=='delivery',Order.address!='').order_by(Order.id.desc()).limit(1))
    return {'phone':user.phone or (previous.phone if previous else ''),'address':previous.address if previous else ''}

@app.post(prefix+'/orders',status_code=201)
def place_order(data:OrderIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    require(user,('customer',))
    return idempotent(db,user,'order.create',idempotency_key,data.model_dump(mode='json'),lambda:create_order(db,user,data))

def order_view(db,o,user):
    b=db.get(Branch,o.branch_id)
    delivery_user=db.get(User,o.assigned_delivery_user_id) if o.assigned_delivery_user_id else None
    result={**row(o),'number':f'ORD-{o.id:06d}','branch_name':b.name,'branch_address':b.address,'customer_name':db.get(User,o.user_id).name,'assigned_delivery_name':delivery_user.name if delivery_user else None}
    if user.role!='customer': result.pop('pickup_code',None)
    result['items']=[row(x) for x in db.scalars(select(OrderItem).where(OrderItem.order_id==o.id)).all()]
    events=db.scalars(select(OrderEvent).where(OrderEvent.order_id==o.id).order_by(OrderEvent.id)).all()
    result['events']=[row(x) for x in events]
    result['payment_collection']=collection_view(db,o)
    if user.role=='customer':
        result['assigned_delivery_name']=None
        for event in result['events']:
            event['tone']='success' if event['status'] in ('completed','payment_received') else 'error' if event['status'] in ('cancelled','rejected','delivery_failed') else 'neutral'
            if event['status']=='delivery_assigned':
                event['display_status']='dispatched'
                event['note']=''
            elif event['status']=='dispatched':
                event['display_status']='delivery_started'
                event['note']='Delivery person started the trip.'
        if result['payment_collection']:
            result['payment_collection']['collected_by']='Store / delivery team'
    last_actor=db.get(User,events[-1].actor_id) if events and events[-1].actor_id else None
    store_rejected=(o.status=='cancelled' and events and (events[-1].status=='rejected' or (last_actor and last_actor.role in ('admin','manager'))))
    result['display_status']='rejected' if store_rejected else o.status
    if user.role=='customer' and result['display_status']=='rejected': result['status']='rejected'
    return result

@app.get(prefix+'/orders')
def orders(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    q=select(Order)
    if user.role=='customer': q=q.where(Order.user_id==user.id)
    else:
        require(user,('admin','manager'))
        if user.role!='admin': q=q.where(Order.branch_id==user.branch_id)
        elif branch_id: q=q.where(Order.branch_id==branch_id)
    q=q.order_by(case((Order.status=='approval_pending',0),else_=1),Order.id.desc()).limit(200)
    return [order_view(db,o,user) for o in db.scalars(q).all()]

@app.get(prefix+'/orders/{ident}')
def order_detail(ident:int,user:User=UserDep,db:DBSession=DB):
    o=get_or_404(db,Order,ident)
    if user.role=='customer':
        if o.user_id!=user.id: raise HTTPException(404,'Order not found.')
    elif user.role=='delivery':
        if o.assigned_delivery_user_id!=user.id:raise HTTPException(404,'Delivery not found.')
    else: scope(user,o.branch_id,('admin','manager'))
    return order_view(db,o,user)

@app.post(prefix+'/orders/{ident}/transition')
def order_transition(ident:int,data:TransitionIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    return idempotent(db,user,f'order.transition.{ident}',idempotency_key,data.model_dump(),lambda:transition(db,user,ident,data))

@app.post(prefix+'/orders/{ident}/payment')
def record_payment(ident:int,data:OrderPaymentIn,user:User=UserDep,db:DBSession=DB):
    order=collection_order(db,user,ident,True)
    return record_collection(db,user,order,data)

@app.post(prefix+'/orders/{ident}/payment/preview')
def preview_order_payment(ident:int,data:OrderPaymentIn,user:User=UserDep,db:DBSession=DB):
    order=collection_order(db,user,ident)
    if order.payment_status=='paid':raise HTTPException(409,'Payment is already recorded. Refresh this order.')
    return settlement_quote(order,data)

@app.get(prefix+'/delivery/staff')
def delivery_staff(branch_id:int,user:User=UserDep,db:DBSession=DB):
    scope(user,branch_id,('admin','manager'))
    return [user_view(x) for x in db.scalars(select(User).where(User.role=='delivery',User.branch_id==branch_id,User.active==True).order_by(User.name)).all()]

@app.post(prefix+'/orders/{ident}/assign-delivery')
def assign_delivery(ident:int,data:DeliveryAssignmentIn,user:User=UserDep,db:DBSession=DB):
    order=get_or_404(db,Order,ident,True);scope(user,order.branch_id,('admin','manager'))
    if order.method!='delivery' or order.status!='ready':raise HTTPException(409,'Only ready delivery orders can be assigned.')
    driver=get_or_404(db,User,data.delivery_user_id)
    if driver.role!='delivery' or not driver.active or driver.branch_id!=order.branch_id:raise HTTPException(422,'Select an active delivery person assigned to this branch.')
    if order.assigned_delivery_user_id==driver.id:return order_view(db,order,user)
    order.assigned_delivery_user_id=driver.id;order.delivery_assigned_at=now()
    db.add(OrderEvent(order_id=order.id,status='delivery_assigned',actor_id=user.id,note=f'Assigned to {driver.name}.'))
    audit(db,user,'order.delivery.assign',order.id,delivery_user_id=driver.id)
    return order_view(db,order,user)

@app.get(prefix+'/delivery/orders')
def delivery_orders(user:User=UserDep,db:DBSession=DB):
    require(user,('delivery',))
    rows=db.scalars(select(Order).where(Order.assigned_delivery_user_id==user.id,Order.method=='delivery',Order.status.in_(('ready','dispatched'))).order_by(Order.delivery_assigned_at,Order.id)).all()
    return [order_view(db,order,user) for order in rows]

@app.get(prefix+'/delivery/profile')
def delivery_profile(user:User=UserDep,db:DBSession=DB):
    require(user,('delivery',))
    branch=db.get(Branch,user.branch_id) if user.branch_id else None
    base=select(func.count()).select_from(Order).where(Order.assigned_delivery_user_id==user.id,Order.method=='delivery')
    return {'name':user.name,'email':user.email,'phone':user.phone,'branch_name':branch.name if branch else None,
        'completed':db.scalar(base.where(Order.status=='completed')),
        'active':db.scalar(base.where(Order.status.in_(('ready','dispatched')))),
        'failed_attempts':db.scalar(select(func.count()).select_from(OrderEvent).where(OrderEvent.actor_id==user.id,OrderEvent.status=='delivery_failed'))}

@app.get(prefix+'/delivery/history')
def delivery_history(status:str=Query(default='all',pattern='^(all|completed|cancelled|rejected)$'),page:int=Query(default=1,ge=1),user:User=UserDep,db:DBSession=DB):
    require(user,('delivery',))
    query=select(Order).where(Order.assigned_delivery_user_id==user.id,Order.method=='delivery',Order.status.in_(('completed','cancelled','rejected')))
    if status!='all':query=query.where(Order.status==status)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    orders=db.scalars(query.order_by(Order.id.desc()).offset((page-1)*20).limit(20)).all()
    return {'items':[order_view(db,o,user) for o in orders],'total':total,'page':page,'page_size':20}

@app.post(prefix+'/delivery/orders/{ident}/start')
def delivery_start(ident:int,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    require(user,('delivery',))
    def apply():
        order=get_or_404(db,Order,ident,True)
        if order.assigned_delivery_user_id!=user.id:raise HTTPException(404,'Delivery not found.')
        if order.status!='ready':raise HTTPException(409,'This order is not ready to start delivery.')
        if not order.reserved_active:raise HTTPException(409,'Reserved stock is no longer active.')
        items=db.scalars(select(OrderItem).where(OrderItem.order_id==order.id)).all();stocks=lock_stock(db,order.branch_id,[x.variant_id for x in items])
        for item in items:
            stock=stocks[item.variant_id];stock.on_hand-=item.quantity;stock.reserved-=item.quantity
            db.add(Movement(branch_id=order.branch_id,variant_id=item.variant_id,delta=-item.quantity,kind='order_fulfilment',reference=f'ORD-{order.id}',actor_id=user.id))
        order.reserved_active=False;order.status='dispatched'
        db.add(OrderEvent(order_id=order.id,status='dispatched',actor_id=user.id,note='Delivery person started the trip.'))
        audit(db,user,'delivery.start',order.id);return order_view(db,order,user)
    return idempotent(db,user,f'delivery.start.{ident}',idempotency_key,{},apply)

@app.post(prefix+'/delivery/orders/{ident}/complete')
def delivery_complete(ident:int,data:DeliveryCompleteIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    require(user,('delivery',))
    def apply():
        order=get_or_404(db,Order,ident,True)
        if order.assigned_delivery_user_id!=user.id:raise HTTPException(404,'Delivery not found.')
        if order.status!='dispatched':raise HTTPException(409,'Start this delivery before completing it.')
        if not secrets.compare_digest(order.pickup_code,data.otp):raise HTTPException(422,'Enter the correct customer delivery OTP.')
        if order.payment_status!='paid':raise HTTPException(409,'Record cash collection before completing delivery.')
        order.status='completed';db.add(OrderEvent(order_id=order.id,status='completed',actor_id=user.id,note='Delivered after customer OTP verification.'))
        audit(db,user,'delivery.complete',order.id);return {'id':order.id,'status':'completed'}
    return idempotent(db,user,f'delivery.complete.{ident}',idempotency_key,data.model_dump(),apply)

@app.post(prefix+'/delivery/orders/{ident}/failed')
def delivery_failed(ident:int,data:DeliveryFailureIn,user:User=UserDep,db:DBSession=DB):
    require(user,('delivery',));order=get_or_404(db,Order,ident,True)
    if order.assigned_delivery_user_id!=user.id:raise HTTPException(404,'Delivery not found.')
    if order.status!='dispatched':raise HTTPException(409,'Only an active delivery can be marked unsuccessful.')
    reason=data.reason.strip();db.add(OrderEvent(order_id=order.id,status='delivery_failed',actor_id=user.id,note=reason));audit(db,user,'delivery.failed',order.id,reason=reason)
    return {'ok':True}

@app.post(prefix+'/delivery/orders/{ident}/location')
def delivery_location(ident:int,data:DeliveryLocationIn,user:User=UserDep,db:DBSession=DB):
    require(user,('delivery',));order=get_or_404(db,Order,ident,True)
    if order.assigned_delivery_user_id!=user.id:raise HTTPException(404,'Delivery not found.')
    if order.status!='dispatched':raise HTTPException(409,'Location sharing is available only during an active delivery.')
    order.driver_latitude=Decimal(str(data.latitude));order.driver_longitude=Decimal(str(data.longitude));order.driver_location_updated_at=now()
    return {'ok':True,'updated_at':order.driver_location_updated_at}

@app.get(prefix+'/orders/{ident}/tracking')
def order_tracking(ident:int,user:User=UserDep,db:DBSession=DB):
    order=get_or_404(db,Order,ident)
    if order.method!='delivery':raise HTTPException(409,'Tracking is available only for delivery orders.')
    if user.role=='delivery':
        if order.assigned_delivery_user_id!=user.id:raise HTTPException(404,'Delivery not found.')
    else:scope(user,order.branch_id,('admin','manager'))
    driver=db.get(User,order.assigned_delivery_user_id) if order.assigned_delivery_user_id else None
    return {'id':order.id,'number':f'ORD-{order.id:06d}','status':order.status,'display_status':order_view(db,order,user)['display_status'],'branch_name':db.get(Branch,order.branch_id).name,'driver_name':driver.name if driver else None,'destination_latitude':str(order.latitude) if order.latitude is not None else None,'destination_longitude':str(order.longitude) if order.longitude is not None else None,'driver_latitude':str(order.driver_latitude) if order.driver_latitude is not None else None,'driver_longitude':str(order.driver_longitude) if order.driver_longitude is not None else None,'location_updated_at':order.driver_location_updated_at,'events':[row(x) for x in db.scalars(select(OrderEvent).where(OrderEvent.order_id==order.id).order_by(OrderEvent.id)).all()]}

@app.get(prefix+'/delivery/operations')
def delivery_operations(branch_id:int|None=Query(default=None,gt=0),driver_id:int|None=Query(default=None,gt=0),status:str='all',from_date:Date|None=None,to_date:Date|None=None,search:str=Query(default='',max_length=100),page:int=Query(default=1,ge=1),page_size:int=Query(default=25,ge=1,le=100),user:User=UserDep,db:DBSession=DB):
    return operations_report(db,user,branch_id,driver_id,status,from_date,to_date,search,page,page_size)

@app.get(prefix+'/delivery/operations/{ident}')
def delivery_operations_detail(ident:int,user:User=UserDep,db:DBSession=DB):
    require(user,('admin','manager'))
    order=get_or_404(db,Order,ident)
    report=operations_detail(db,user,order)
    return {**order_view(db,order,user),**report}

@app.get(prefix+'/delivery/management')
def delivery_management(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    require(user,('admin','manager'))
    if user.role=='manager':branch_id=user.branch_id
    q=select(Order).where(Order.method=='delivery',Order.status.in_(('ready','dispatched','completed')))
    if branch_id:q=q.where(Order.branch_id==branch_id)
    result=[]
    for order in db.scalars(q.order_by(Order.id.desc()).limit(200)).all():
        customer=db.get(User,order.user_id);driver=db.get(User,order.assigned_delivery_user_id) if order.assigned_delivery_user_id else None
        result.append({'id':order.id,'number':f'ORD-{order.id:06d}','branch_name':db.get(Branch,order.branch_id).name,'customer_name':customer.name,'customer_phone':order.phone,'address':order.address,'destination_latitude':str(order.latitude) if order.latitude is not None else None,'destination_longitude':str(order.longitude) if order.longitude is not None else None,'status':order.status,'driver_name':driver.name if driver else None,'assigned_at':order.delivery_assigned_at,'driver_latitude':str(order.driver_latitude) if order.driver_latitude is not None else None,'driver_longitude':str(order.driver_longitude) if order.driver_longitude is not None else None,'location_updated_at':order.driver_location_updated_at,'created_at':order.created_at})
    return result

@app.get(prefix+'/inventory')
def inventory(branch_id:int|None=None,threshold:Decimal|None=Query(default=None,ge=0,le=100000),comparison:str|None=Query(default=None,pattern='^(lt|gt)$'),user:User=UserDep,db:DBSession=DB):
    if branch_id is None: require(user,('admin',))
    else: scope(user,branch_id)
    if (threshold is None)!=(comparison is None):raise HTTPException(422,'Threshold and comparison must be provided together.')
    statement=select(Stock)
    if branch_id is not None: statement=statement.where(Stock.branch_id==branch_id)
    if threshold is not None:
        availability=Stock.on_hand-Stock.reserved-Stock.damaged
        statement=statement.where(availability<threshold if comparison=='lt' else availability>threshold)
    stocks=db.scalars(statement.order_by(Stock.variant_id)).all()
    result=[]
    for s in stocks:
        v=db.get(Variant,s.variant_id);p=db.get(Product,v.product_id)
        result.append({**row(s),'branch_name':db.get(Branch,s.branch_id).name,'name':p.name,'label':v.label,'sku':v.sku,'unit':v.unit,'price':v.price,'available':available(s),'low':available(s)<=s.reorder})
    return result

@app.get(prefix+'/inventory/barcodes')
def inventory_barcodes(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    if branch_id is None:require(user,('admin',))
    else:scope(user,branch_id,('admin','manager','inventory'))
    statement=select(Stock)
    if branch_id is not None:statement=statement.where(Stock.branch_id==branch_id)
    result={}
    for stock in db.scalars(statement).all():
        quantity=available(stock)
        if quantity<=0:continue
        variant=db.get(Variant,stock.variant_id);product=db.get(Product,variant.product_id) if variant else None
        if not variant or not product or not variant.active or not product.active:continue
        current=result.setdefault(variant.id,{'variant_id':variant.id,'name':product.name,'label':variant.label,'sku':variant.sku,'unit':variant.unit,'available':'0'})
        current['available']=str(Decimal(current['available'])+quantity)
    return sorted(result.values(),key=lambda item:(item['name'].lower(),item['label'].lower()))

@app.get(prefix+'/inventory/barcodes/{variant_id}.svg')
def inventory_barcode_svg(variant_id:int,branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    if branch_id is None:require(user,('admin',))
    else:scope(user,branch_id,('admin','manager','inventory'))
    variant=get_or_404(db,Variant,variant_id);product=get_or_404(db,Product,variant.product_id)
    statement=select(Stock).where(Stock.variant_id==variant_id)
    if branch_id is not None:statement=statement.where(Stock.branch_id==branch_id)
    if not any(available(stock)>0 for stock in db.scalars(statement).all()) or not variant.active or not product.active:raise HTTPException(404,'No stocked product found for this barcode.')
    try:svg=code128_svg(variant.sku)
    except ValueError as error:raise HTTPException(422,str(error))
    return Response(content=svg,media_type='image/svg+xml',headers={'Cache-Control':'private, max-age=300'})

@app.get(prefix+'/inventory/barcode-sheet',response_class=HTMLResponse)
def inventory_barcode_sheet(user:User=UserDep,db:DBSession=DB):
    require(user,('admin','manager','inventory'))
    branch_id=None if user.role=='admin' else user.branch_id
    items=inventory_barcodes(branch_id,user,db)
    labels=[]
    for item in items:
        try:barcode=code128_svg(item['sku'])
        except ValueError:continue
        labels.append(f'<article><strong>{escape(item["name"])}</strong><span>{escape(item["label"])}</span>{barcode}<code>{escape(item["sku"])}</code></article>')
    scope_name='All branches' if branch_id is None else escape(db.get(Branch,branch_id).name)
    return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><title>CHINNU barcode labels</title><style>body{{font-family:Arial,sans-serif;color:#172e23;margin:24px}}header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}}h1{{font-size:22px;margin:0}}button{{background:#1f573f;color:white;border:0;border-radius:7px;padding:10px 16px;font-weight:bold}}main{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}article{{border:1px dashed #8d9990;border-radius:6px;padding:12px;text-align:center;break-inside:avoid}}article strong,article span,article code{{display:block}}article span{{font-size:12px;margin:4px 0 8px}}article svg{{width:100%;height:56px}}article code{{font-size:12px;margin-top:6px}}@media print{{body{{margin:0}}header button{{display:none}}main{{gap:4mm}}article{{padding:4mm}}@page{{size:A4;margin:8mm}}}}</style></head><body><header><div><h1>CHINNU barcode labels</h1><small>{scope_name} · {len(labels)} stocked selling options</small></div><button onclick="window.print()">Print labels</button></header><main>{''.join(labels) if labels else '<p>No stocked products are available.</p>'}</main></body></html>''')

@app.get(prefix+'/movements')
def movements(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    if branch_id is None: require(user,('admin',))
    else: scope(user,branch_id)
    statement=select(Movement)
    if branch_id is not None: statement=statement.where(Movement.branch_id==branch_id)
    result=[]
    for m in db.scalars(statement.order_by(Movement.id.desc()).limit(200)).all():
        v=db.get(Variant,m.variant_id);p=db.get(Product,v.product_id)
        result.append({**row(m),'branch_name':db.get(Branch,m.branch_id).name,'name':f'{p.name} · {v.label}'})
    return result

@app.post(prefix+'/inventory/change')
def inventory_change(data:StockIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    scope(user,data.branch_id,('admin','manager','inventory'))
    if data.kind.startswith('adjust'): require(user,('admin','manager'))
    stock_quantity(db,data.variant_id,data.quantity)
    def apply():
        s=lock_stock(db,data.branch_id,[data.variant_id])[data.variant_id]
        if data.kind in ('damage','adjust_down') and available(s)<data.quantity: raise HTTPException(409,'This change would consume reserved or unavailable stock.')
        delta=data.quantity if data.kind in ('receive','adjust_up') else -data.quantity
        if data.kind=='damage': s.damaged+=data.quantity;delta=Decimal(0)
        else: s.on_hand+=delta
        db.add(Movement(branch_id=data.branch_id,variant_id=data.variant_id,delta=delta,kind=data.kind,reference='manual',reason=data.reason,actor_id=user.id))
        audit(db,user,'inventory.'+data.kind,s.id,quantity=str(data.quantity),reason=data.reason)
        return {'ok':True}
    return idempotent(db,user,'inventory.change',idempotency_key,data.model_dump(mode='json'),apply)

@app.post(prefix+'/sales',status_code=201)
def sale_create(data:SaleIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    scope(user,data.branch_id,('admin','manager','cashier'))
    b=get_or_404(db,Branch,data.branch_id)
    if not b.active: raise HTTPException(409,'Branch is inactive.')
    return idempotent(db,user,'sale.create',idempotency_key,data.model_dump(mode='json'),lambda:create_sale(db,user,data))

@app.get(prefix+'/pos-customers/lookup')
def pos_customer_lookup(mobile:str=Query(pattern=r'^[6-9][0-9]{9}$'),user:User=UserDep,db:DBSession=DB):
    require(user,('admin','manager','cashier'))
    customer=db.scalar(select(POSCustomer).where(POSCustomer.mobile==mobile))
    account=db.scalar(select(User).where(User.role=='customer',User.phone==mobile))
    return {'found':customer is not None or account is not None,'name':account.name if account else customer.name if customer else None,'customer_code':customer.public_code if customer else None}

@app.get(prefix+'/pos/scan')
def pos_scan(code:str=Query(min_length=2,max_length=60),branch_id:int=Query(gt=0),user:User=UserDep,db:DBSession=DB):
    scope(user,branch_id,('manager','cashier'))
    shift=db.scalar(select(Shift.id).where(Shift.actor_id==user.id,Shift.branch_id==branch_id,Shift.closed_at==None))
    if shift is None:raise HTTPException(409,'Open your cashier shift before adding products to the bill.')
    branch=get_or_404(db,Branch,branch_id)
    if not branch.active:raise HTTPException(409,'This branch is inactive.')
    clean=code.strip()
    variant=db.scalar(select(Variant).where(func.lower(Variant.sku)==clean.lower(),Variant.active==True))
    if not variant:raise HTTPException(404,'No active product matches this barcode or SKU.')
    product=db.get(Product,variant.product_id)
    if not product or not product.active:raise HTTPException(404,'No active product matches this barcode or SKU.')
    stock=db.scalar(select(Stock).where(Stock.branch_id==branch_id,Stock.variant_id==variant.id))
    if not stock:raise HTTPException(409,'This product is not configured for the working branch.')
    quantity=available(stock)
    if quantity<variant.min_qty:raise HTTPException(409,f'{product.name} is out of stock at this branch.')
    return {'variant_id':variant.id,'sku':variant.sku,'name':product.name,'label':variant.label,'unit':variant.unit,'price':str(variant.price),'min_qty':str(variant.min_qty),'step':str(variant.step),'max_qty':str(variant.max_qty),'available':str(quantity),'requires_quantity':variant.unit in ('kg','litre')}

def sale_view(db,s):
    account=db.scalar(select(User).where(User.role=='customer',User.phone==s.customer_mobile))
    payments=[row(x) for x in db.scalars(select(SalePayment).where(SalePayment.sale_id==s.id).order_by(SalePayment.id)).all()]
    return {**row(s),'customer_name':account.name if account else s.customer_name,'number':f'POS-{s.id:06d}','branch_name':db.get(Branch,s.branch_id).name,'payments':payments,'items':[row(x) for x in db.scalars(select(SaleItem).where(SaleItem.sale_id==s.id)).all()]}

def return_exchange_view(db,transaction):
    sale=db.get(Sale,transaction.sale_id)
    account=db.scalar(select(User).where(User.role=='customer',User.phone==sale.customer_mobile))
    return {**row(transaction),'number':f"{'EXC' if transaction.kind=='exchange' else 'RET'}-{transaction.id:06d}",'original_receipt':f'POS-{transaction.sale_id:06d}','customer_name':account.name if account else sale.customer_name,'branch_name':db.get(Branch,transaction.branch_id).name}

@app.get(prefix+'/sales')
def sales(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    if branch_id is None: require(user,('admin',))
    else: scope(user,branch_id,('admin','manager','cashier'))
    statement=select(Sale)
    if branch_id is not None: statement=statement.where(Sale.branch_id==branch_id)
    return [sale_view(db,s) for s in db.scalars(statement.order_by(Sale.id.desc()).limit(200)).all()]

@app.get(prefix+'/online-sales')
def online_sales(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    if branch_id is None: require(user,('admin',))
    else: scope(user,branch_id,('admin','manager','cashier'))
    statement=select(Order).where(Order.payment_status=='paid')
    if branch_id is not None: statement=statement.where(Order.branch_id==branch_id)
    return [order_view(db,order,user) for order in db.scalars(statement.order_by(Order.id.desc()).limit(200)).all()]

@app.get(prefix+'/return-exchanges')
def return_exchanges(branch_id:int|None=None,kind:str|None=Query(default=None,pattern='^(exchange|refund)$'),user:User=UserDep,db:DBSession=DB):
    if branch_id is None: require(user,('admin',))
    else: scope(user,branch_id,('admin','manager','cashier'))
    statement=select(ReturnExchange)
    if branch_id is not None: statement=statement.where(ReturnExchange.branch_id==branch_id)
    if kind is not None: statement=statement.where(ReturnExchange.kind==kind)
    transactions=db.scalars(statement.order_by(ReturnExchange.id.desc()).limit(200)).all()
    return [return_exchange_view(db,transaction) for transaction in transactions]

@app.post(prefix+'/sales/{ident}/returns')
def sale_return(ident:int,data:ReturnIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    sale=get_or_404(db,Sale,ident,True);scope(user,sale.branch_id,('admin','manager'))
    def apply():
        item=get_or_404(db,SaleItem,data.item_id,True)
        if item.sale_id!=ident or data.quantity>item.quantity-item.returned: raise HTTPException(409,'Return quantity exceeds the remaining sale quantity.')
        if data.quantity!=item.quantity-item.returned: raise HTTPException(422,'Return the remaining line quantity in one operation.')
        s=lock_stock(db,sale.branch_id,[item.variant_id])[item.variant_id]
        refund=money(item.line_total-money(item.price*item.returned))
        item.returned+=data.quantity;sale.refunded+=refund;s.on_hand+=data.quantity
        if data.condition=='damaged': s.damaged+=data.quantity
        db.add(Movement(branch_id=sale.branch_id,variant_id=item.variant_id,delta=data.quantity,kind='sale_return',reference=f'POS-{ident}',reason=data.reason,actor_id=user.id))
        audit(db,user,'sale.cash_refund',ident,amount=str(refund),condition=data.condition,reason=data.reason)
        return {'refund':str(refund)}
    return idempotent(db,user,f'sale.return.{ident}',idempotency_key,data.model_dump(mode='json'),apply)

@app.get(prefix+'/return-sales')
def return_sales(branch_id:int|None=None,q:str=Query(min_length=3,max_length=30),user:User=UserDep,db:DBSession=DB):
    if branch_id is None: require(user,('admin',))
    else: scope(user,branch_id,('admin','manager'))
    normalized=q.strip().upper();statement=select(Sale)
    if branch_id is not None: statement=statement.where(Sale.branch_id==branch_id)
    if normalized.startswith('POS-') and normalized[4:].isdigit():statement=statement.where(Sale.id==int(normalized[4:]))
    elif q.strip().isdigit():statement=statement.where(Sale.customer_mobile==q.strip())
    else:return []
    return [sale_view(db,s) for s in db.scalars(statement.order_by(Sale.id.desc()).limit(50)).all()]

def exchange_quote(db,sale,data):
    return_total=Decimal(0)
    for requested in data.returns:
        item=get_or_404(db,SaleItem,requested.item_id)
        if item.sale_id!=sale.id:raise HTTPException(409,'A return line does not belong to this receipt.')
        if requested.quantity>item.quantity-item.returned:raise HTTPException(409,'Return quantity exceeds the remaining returnable quantity.')
        stock_quantity(db,item.variant_id,requested.quantity);return_total+=money(item.price*requested.quantity)
    replacements=lines(db,data.replacements) if data.replacements else []
    replacement_total=sum((x['line_total'] for x in replacements),Decimal(0))
    return_total=money(return_total);replacement_total=money(replacement_total)
    return {'return_total':format(return_total,'.2f'),'replacement_total':format(replacement_total,'.2f'),'amount_due':format(money(max(replacement_total-return_total,Decimal(0))),'.2f'),'refund_due':format(money(max(return_total-replacement_total,Decimal(0))),'.2f')}

@app.post(prefix+'/sales/{ident}/return-exchange/quote')
def return_exchange_quote(ident:int,data:ReturnExchangeIn,user:User=UserDep,db:DBSession=DB):
    sale=get_or_404(db,Sale,ident);scope(user,sale.branch_id,('admin','manager'))
    return exchange_quote(db,sale,data)

@app.post(prefix+'/sales/{ident}/return-exchange')
def return_exchange(ident:int,data:ReturnExchangeIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    sale=get_or_404(db,Sale,ident,True);scope(user,sale.branch_id,('admin','manager'))
    def apply():
        shift=db.scalar(select(Shift).where(Shift.actor_id==user.id,Shift.branch_id==sale.branch_id,Shift.closed_at==None).with_for_update())
        if not shift:raise HTTPException(409,'Open your cashier shift before processing a return or exchange.')
        originals=[]
        for requested in data.returns:
            item=get_or_404(db,SaleItem,requested.item_id,True)
            if item.sale_id!=sale.id:raise HTTPException(409,'A return line does not belong to this receipt.')
            if requested.quantity>item.quantity-item.returned:raise HTTPException(409,'Return quantity exceeds the remaining returnable quantity.')
            stock_quantity(db,item.variant_id,requested.quantity)
            originals.append((requested,item))
        replacements=lines(db,data.replacements) if data.replacements else []
        variant_ids={item.variant_id for _,item in originals}|{x['variant_id'] for x in replacements}
        stocks=lock_stock(db,sale.branch_id,variant_ids)
        returned_rows=[];return_total=Decimal(0)
        for requested,item in originals:
            value=money(item.price*requested.quantity);return_total+=value;item.returned+=requested.quantity
            stock=stocks[item.variant_id];stock.on_hand+=requested.quantity
            if requested.condition=='damaged':stock.damaged+=requested.quantity
            returned_rows.append({'item_id':item.id,'variant_id':item.variant_id,'name':item.name,'unit':item.unit,'quantity':str(requested.quantity),'price':str(item.price),'line_total':str(value),'condition':requested.condition})
            db.add(Movement(branch_id=sale.branch_id,variant_id=item.variant_id,delta=requested.quantity,kind='exchange_return',reference=f'POS-{sale.id}',reason=data.reason,actor_id=user.id))
        replacement_rows=[];replacement_total=Decimal(0)
        for replacement in replacements:
            stock=stocks[replacement['variant_id']]
            if available(stock)<replacement['quantity']:raise HTTPException(409,f"Only {available(stock)} available for {replacement['name']}.")
            stock.on_hand-=replacement['quantity'];replacement_total+=replacement['line_total']
            replacement_rows.append({k:str(v) if isinstance(v,Decimal) else v for k,v in replacement.items()})
            db.add(Movement(branch_id=sale.branch_id,variant_id=replacement['variant_id'],delta=-replacement['quantity'],kind='exchange_issue',reference=f'POS-{sale.id}',reason=data.reason,actor_id=user.id))
        return_total=money(return_total);replacement_total=money(replacement_total)
        amount_due=money(max(replacement_total-return_total,Decimal(0)));refund_due=money(max(return_total-replacement_total,Decimal(0)))
        if data.settlement_method=='cash' and amount_due>0:
            if data.amount_tendered is None:raise HTTPException(422,'Enter the cash received from the customer.')
            if data.amount_tendered<amount_due:raise HTTPException(422,'Cash received cannot be less than the exchange balance.')
            amount_tendered=money(data.amount_tendered);change_due=money(amount_tendered-amount_due)
        else:
            if data.amount_tendered is not None:raise HTTPException(422,'Cash received is only used when the customer owes a cash balance.')
            amount_tendered=None;change_due=Decimal(0)
        sale.refunded+=return_total
        transaction=ReturnExchange(sale_id=sale.id,branch_id=sale.branch_id,actor_id=user.id,shift_id=shift.id,customer_code=sale.customer_code,kind='exchange' if replacements else 'refund',returned_items=returned_rows,replacement_items=replacement_rows,return_total=return_total,replacement_total=replacement_total,amount_due=amount_due,refund_due=refund_due,settlement_method=data.settlement_method,amount_tendered=amount_tendered,change_due=change_due,reason=data.reason)
        db.add(transaction);db.flush();audit(db,user,'sale.return_exchange',transaction.id,sale_id=sale.id,amount_due=str(amount_due),refund_due=str(refund_due))
        return return_exchange_view(db,transaction)
    return idempotent(db,user,f'sale.return_exchange.{ident}',idempotency_key,data.model_dump(mode='json'),apply)

@app.get(prefix+'/transfers')
def transfer_list(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    require(user,('admin','manager','inventory'))
    q=select(Transfer)
    if user.role!='admin': q=q.where(or_(Transfer.source_id==user.branch_id,Transfer.target_id==user.branch_id))
    elif branch_id is not None: q=q.where(or_(Transfer.source_id==branch_id,Transfer.target_id==branch_id))
    result=[]
    for t in db.scalars(q.order_by(Transfer.id.desc()).limit(200)).all():
        v=db.get(Variant,t.variant_id);p=db.get(Product,v.product_id)
        result.append({**row(t),'source':db.get(Branch,t.source_id).name,'target':db.get(Branch,t.target_id).name,'name':f'{p.name} · {v.label}'})
    return result

@app.post(prefix+'/transfers')
def transfer_create(data:TransferIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    scope(user,data.source_id,('admin','manager','inventory'))
    if data.source_id==data.target_id: raise HTTPException(422,'Choose a different destination.')
    get_or_404(db,Branch,data.target_id)
    stock_quantity(db,data.variant_id,data.quantity)
    def apply():
        s=lock_stock(db,data.source_id,[data.variant_id])[data.variant_id]
        if available(s)<data.quantity: raise HTTPException(409,'Insufficient available source stock.')
        t=Transfer(**data.model_dump(),actor_id=user.id);db.add(t);db.flush();s.on_hand-=data.quantity
        db.add(Movement(branch_id=data.source_id,variant_id=data.variant_id,delta=-data.quantity,kind='transfer_dispatch',reference=f'TR-{t.id}',actor_id=user.id))
        audit(db,user,'transfer.dispatch',t.id)
        return {'id':t.id}
    return idempotent(db,user,'transfer.create',idempotency_key,data.model_dump(mode='json'),apply)

@app.post(prefix+'/transfers/{ident}/receive')
def transfer_receive(ident:int,data:QuantityIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    t=get_or_404(db,Transfer,ident,True);scope(user,t.target_id,('admin','manager','inventory'))
    stock_quantity(db,t.variant_id,data.quantity)
    def apply():
        if t.status=='received' or data.quantity>t.quantity-t.received: raise HTTPException(409,'Received quantity exceeds stock in transit.')
        s=lock_stock(db,t.target_id,[t.variant_id])[t.variant_id]
        s.on_hand+=data.quantity;t.received+=data.quantity
        if t.received==t.quantity:t.status='received'
        db.add(Movement(branch_id=t.target_id,variant_id=t.variant_id,delta=data.quantity,kind='transfer_receive',reference=f'TR-{ident}',actor_id=user.id))
        audit(db,user,'transfer.receive',ident,quantity=str(data.quantity))
        return {'ok':True}
    return idempotent(db,user,f'transfer.receive.{ident}',idempotency_key,data.model_dump(mode='json'),apply)

@app.get(prefix+'/suppliers')
def supplier_list(user:User=UserDep,db:DBSession=DB):
    require(user,('admin','manager','inventory'))
    return [row(s) for s in db.scalars(select(Supplier).order_by(Supplier.name)).all()]

@app.post(prefix+'/suppliers')
def supplier_create(data:SupplierIn,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',));s=Supplier(**data.model_dump());db.add(s);db.flush();audit(db,user,'supplier.create',s.id)
    return row(s)

@app.get(prefix+'/purchases')
def purchases(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    require(user,('admin','manager','inventory'));q=select(Purchase)
    if user.role!='admin':q=q.where(Purchase.branch_id==user.branch_id)
    elif branch_id is not None:q=q.where(Purchase.branch_id==branch_id)
    result=[]
    for x in db.scalars(q.order_by(Purchase.id.desc()).limit(200)).all():
        v=db.get(Variant,x.variant_id);p=db.get(Product,v.product_id)
        profit=money(v.price-x.unit_cost);margin=money((profit/v.price)*100) if v.price else Decimal(0)
        result.append({**row(x),'branch_name':db.get(Branch,x.branch_id).name,'name':f'{p.name} · {v.label}','supplier':db.get(Supplier,x.supplier_id).name,'selling_price':format(money(v.price),'.2f'),'profit_per_unit':format(profit,'.2f'),'margin_percent':format(margin,'.2f')})
    return result

@app.post(prefix+'/purchases')
def purchase_create(data:PurchaseIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    scope(user,data.branch_id,('admin','manager'));get_or_404(db,Supplier,data.supplier_id);get_or_404(db,Variant,data.variant_id)
    stock_quantity(db,data.variant_id,data.quantity)
    def apply():
        p=Purchase(**data.model_dump());db.add(p);db.flush();audit(db,user,'purchase.create',p.id)
        return {'id':p.id}
    return idempotent(db,user,'purchase.create',idempotency_key,data.model_dump(mode='json'),apply)

@app.post(prefix+'/purchases/{ident}/receive')
def purchase_receive(ident:int,data:PurchaseReceiveIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    p=get_or_404(db,Purchase,ident,True);scope(user,p.branch_id,('admin','manager','inventory'))
    stock_quantity(db,p.variant_id,data.quantity)
    def apply():
        if data.quantity>p.quantity-p.received: raise HTTPException(409,'Received quantity exceeds outstanding quantity.')
        if p.received>0 and data.unit_cost!=p.unit_cost: raise HTTPException(409,'Buying price cannot change after a partial receipt. Create a separate purchase for stock at a different price.')
        p.unit_cost=money(data.unit_cost)
        s=lock_stock(db,p.branch_id,[p.variant_id])[p.variant_id];s.on_hand+=data.quantity;p.received+=data.quantity
        if p.received==p.quantity:p.status='received'
        db.add(Movement(branch_id=p.branch_id,variant_id=p.variant_id,delta=data.quantity,kind='purchase_receive',reference=f'PO-{ident}',actor_id=user.id))
        audit(db,user,'purchase.receive',ident,quantity=str(data.quantity),unit_cost=str(p.unit_cost))
        return {'ok':True,'unit_cost':str(p.unit_cost)}
    return idempotent(db,user,f'purchase.receive.{ident}',idempotency_key,data.model_dump(mode='json'),apply)

@app.get(prefix+'/admin/product-categories')
def product_categories(user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    return list(db.scalars(select(Product.category).distinct().order_by(Product.category)).all())

@app.post(prefix+'/admin/products')
def product_create(data:ProductIn,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',));p=Product(**data.model_dump(exclude={'variants'}));db.add(p);db.flush()
    for variant in data.variants:
        v=Variant(product_id=p.id,**variant.model_dump());db.add(v);db.flush()
        for b in db.scalars(select(Branch)).all():db.add(Stock(branch_id=b.id,variant_id=v.id,on_hand=0,reserved=0,damaged=0))
    audit(db,user,'product.create',p.id)
    return {'id':p.id,'code':product_code(p)}

@app.put(prefix+'/admin/products/{ident}')
def product_update(ident:int,data:ProductUpdateIn,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    product=get_or_404(db,Product,ident,True)
    existing={v.id:v for v in db.scalars(select(Variant).where(Variant.product_id==ident).with_for_update()).all()}
    ids=[v.id for v in data.variants if v.id is not None]
    if len(ids)!=len(set(ids)) or set(ids)!=set(existing):
        raise HTTPException(422,'Include every existing selling option exactly once. Options cannot be deleted or moved between products.')
    skus=[v.sku for v in data.variants]
    if len(skus)!=len(set(skus)):
        raise HTTPException(422,'Each selling option needs a unique SKU / barcode.')
    for entry in data.variants:
        duplicate=db.scalar(select(Variant.id).where(Variant.sku==entry.sku,Variant.id!=entry.id) if entry.id else select(Variant.id).where(Variant.sku==entry.sku))
        if duplicate:
            raise HTTPException(422,'This SKU / barcode is already used by another selling option.')
        if entry.id and existing[entry.id].unit!=entry.unit:
            used=any(db.scalar(select(model.id).where(model.variant_id==entry.id).limit(1)) for model in (Movement,SaleItem,OrderItem))
            stock=db.scalar(select(Stock.id).where(Stock.variant_id==entry.id,or_(Stock.on_hand!=0,Stock.reserved!=0,Stock.damaged!=0)).limit(1))
            if used or stock:
                raise HTTPException(422,'The unit cannot change after stock or transaction activity. Add a new selling option instead.')
    for key,value in data.model_dump(exclude={'variants'}).items():setattr(product,key,value)
    for entry in data.variants:
        values=entry.model_dump(exclude={'id'})
        if entry.id:
            for key,value in values.items():setattr(existing[entry.id],key,value)
        else:
            variant=Variant(product_id=ident,**values);db.add(variant);db.flush()
            for branch in db.scalars(select(Branch)).all():
                db.add(Stock(branch_id=branch.id,variant_id=variant.id,on_hand=0,reserved=0,damaged=0))
    audit(db,user,'product.update',product.id)
    return {'id':product.id,'code':product_code(product)}

@app.get(prefix+'/admin/products/import-template')
def product_import_template(user:User=UserDep):
    require(user,('admin',))
    path=os.path.join(os.path.dirname(__file__),'assets','chinnu_product_import_template.xlsx')
    return FileResponse(path,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',filename='CHINNU_Product_Import_Template.xlsx')

@app.post(prefix+'/admin/products/bulk-import')
async def product_bulk_import(request:Request,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    try:rows=product_rows(await request.body())
    except ValueError as error:raise HTTPException(422,str(error))
    grouped={};seen_skus=set();errors=[]
    existing_skus=set(db.scalars(select(Variant.sku)).all())
    existing_names={x.lower() for x in db.scalars(select(Product.name)).all()}
    for number,row in enumerate(rows,start=2):
        name=row['product_name'].strip();sku=row['sku'].strip()
        if not name:errors.append(f'Row {number}: product_name is required.');continue
        if not sku:errors.append(f'Row {number}: sku is required.');continue
        sku_key=sku.lower()
        if sku_key in seen_skus or any(x.lower()==sku_key for x in existing_skus):errors.append(f'Row {number}: SKU {sku} is already used.');continue
        seen_skus.add(sku_key)
        key=name.lower();entry=grouped.setdefault(key,{'first_row':number,'name':name,'category':row['category'].strip(),'description':row['description'].strip(),'tone':row['tone'].strip().lower(),'variants':[]})
        if any(entry[field]!=(row[field].strip().lower() if field=='tone' else row[field].strip()) for field in ('category','description','tone')):
            errors.append(f'Row {number}: repeated product details must match row {entry["first_row"]}.');continue
        entry['variants'].append({'sku':sku,'label':row['option_label'].strip(),'unit':row['unit'].strip().lower(),'price':row['price'],'min_qty':row['min_qty'],'step':row['step'],'max_qty':row['max_qty']})
    for entry in grouped.values():
        if entry['name'].lower() in existing_names:errors.append(f'Row {entry["first_row"]}: product {entry["name"]} already exists.')
        try:entry['validated']=ProductIn.model_validate({k:v for k,v in entry.items() if k in ('name','category','description','tone','variants')})
        except ValidationError as error:
            message='; '.join('.'.join(str(p) for p in issue['loc'])+': '+issue['msg'] for issue in error.errors())
            errors.append(f'Row {entry["first_row"]}: {message}')
    if errors:raise HTTPException(422,'Import failed. '+' '.join(errors[:20])+(' More errors were omitted.' if len(errors)>20 else ''))
    created_variants=0
    for entry in grouped.values():
        data=entry['validated'];product=Product(**data.model_dump(exclude={'variants'}));db.add(product);db.flush()
        for item in data.variants:
            variant=Variant(product_id=product.id,**item.model_dump());db.add(variant);db.flush();created_variants+=1
            for branch in db.scalars(select(Branch)).all():db.add(Stock(branch_id=branch.id,variant_id=variant.id,on_hand=0,reserved=0,damaged=0))
    audit(db,user,'product.bulk_import','products',products=len(grouped),variants=created_variants)
    return {'products_created':len(grouped),'variants_created':created_variants}

@app.patch(prefix+'/admin/variants/{ident}/price')
def price_change(ident:int,data:PriceIn,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',));v=get_or_404(db,Variant,ident,True)
    audit(db,user,'price.change',ident,before=str(v.price),after=str(data.price));v.price=data.price
    return {'ok':True}

@app.post(prefix+'/admin/products/{ident}/archive')
def archive(ident:int,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',));p=get_or_404(db,Product,ident);p.active=False;audit(db,user,'product.archive',ident)
    return {'ok':True}

@app.post(prefix+'/admin/branches')
def branch_create(data:BranchIn,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',));values=data.model_dump();values['delivery_slabs']=data.model_dump(mode='json')['delivery_slabs'];b=Branch(**values);db.add(b);db.flush()
    for v in db.scalars(select(Variant)).all():db.add(Stock(branch_id=b.id,variant_id=v.id,on_hand=0,reserved=0,damaged=0))
    audit(db,user,'branch.create',b.id)
    return row(b)

@app.put(prefix+'/admin/branches/{ident}')
def branch_update(ident:int,data:BranchIn,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',));b=get_or_404(db,Branch,ident,True)
    values=data.model_dump();values['delivery_slabs']=data.model_dump(mode='json')['delivery_slabs']
    for k,v in values.items():setattr(b,k,v)
    audit(db,user,'branch.update',ident)
    return row(b)

@app.get(prefix+'/admin/users')
def users(branch_id:int|None=Query(default=None,gt=0),user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    query=select(User).where(User.role!='customer')
    if branch_id is not None:
        get_or_404(db,Branch,branch_id)
        query=query.where(User.branch_id==branch_id)
    return [user_view(u) for u in db.scalars(query.order_by(User.id)).all()]

@app.post(prefix+'/admin/users')
def staff_create(data:StaffIn,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',));get_or_404(db,Branch,data.branch_id)
    u=User(name=data.name,email=data.email.strip().lower(),password_hash=hash_password(data.password),role=data.role,branch_id=data.branch_id)
    db.add(u);db.flush();audit(db,user,'staff.create',u.id)
    return user_view(u)

@app.put(prefix+'/admin/users/{ident}')
def staff_update(ident:int,data:StaffUpdateIn,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',));u=get_or_404(db,User,ident,True)
    if u.role in ('admin','customer'):raise HTTPException(409,'Only manager, cashier, inventory, and delivery accounts can be edited here.')
    get_or_404(db,Branch,data.branch_id)
    email=data.email.strip().lower()
    if '@' not in email or '.' not in email.split('@')[-1]:raise HTTPException(422,'Enter a valid email address.')
    if db.scalar(select(User).where(User.email==email,User.id!=u.id)):raise HTTPException(409,'This email address is already used by another account.')
    before={'name':u.name,'email':u.email,'role':u.role,'branch_id':u.branch_id}
    u.name=data.name.strip();u.email=email;u.role=data.role;u.branch_id=data.branch_id
    password_changed=data.password is not None
    if password_changed:
        u.password_hash=hash_password(data.password)
        db.execute(delete(Session).where(Session.user_id==u.id))
    audit(db,user,'staff.credentials.update',u.id,before=before,after={'name':u.name,'email':u.email,'role':u.role,'branch_id':u.branch_id},password_changed=password_changed)
    return user_view(u)

@app.put(prefix+'/admin/password')
def admin_password_change(data:PasswordChangeIn,request:Request,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    if not user.password_hash or not verify_password(data.current_password,user.password_hash):raise HTTPException(422,'Current password is incorrect.')
    if verify_password(data.new_password,user.password_hash):raise HTTPException(422,'New password must be different from the current password.')
    user.password_hash=hash_password(data.new_password)
    current_token=token_hash(request.cookies.get('grocery_session',''))
    db.execute(delete(Session).where(Session.user_id==user.id,Session.token_hash!=current_token))
    audit(db,user,'admin.password.change',user.id)
    return {'ok':True}

def customer_identity(db,mobile):
    customer=db.scalar(select(POSCustomer).where(POSCustomer.mobile==mobile))
    account=db.scalar(select(User).where(User.role=='customer',User.phone==mobile))
    if not customer and not account:raise HTTPException(404,'Customer not found.')
    return customer,account

def customer_summary(db,mobile):
    customer,account=customer_identity(db,mobile)
    sales_rows=db.scalars(select(Sale).where(Sale.customer_mobile==mobile).order_by(Sale.id.desc())).all()
    orders_rows=db.scalars(select(Order).where(Order.user_id==account.id).order_by(Order.id.desc())).all() if account else []
    sale_ids=[sale.id for sale in sales_rows]
    exchanges=db.scalars(select(ReturnExchange).where(ReturnExchange.sale_id.in_(sale_ids))).all() if sale_ids else []
    completed_orders=[order for order in orders_rows if order.status=='completed']
    lifetime=sum((sale.total-sale.refunded for sale in sales_rows),Decimal(0))+sum((exchange.replacement_total for exchange in exchanges),Decimal(0))+sum((order.total for order in completed_orders),Decimal(0))
    methods={method:sum(sale.payment_method==method for sale in sales_rows) for method in ('cash','card','upi')}
    activity=[x.created_at for x in sales_rows]+[x.created_at for x in orders_rows]
    public_code=customer.public_code if customer else 'CUS-'+hashlib.sha256(mobile.encode()).hexdigest()[:10].upper()
    return {'id':mobile,'name':account.name if account else customer.name,'mobile':mobile,'email':account.email if account else None,'public_code':public_code,'source':'linked' if customer and account else 'online' if account else 'store','visits':len(sales_rows)+len(completed_orders),'pos_purchases':len(sales_rows),'online_orders':len(orders_rows),'lifetime_value':str(money(lifetime)),'returned_value':str(money(sum((sale.refunded for sale in sales_rows),Decimal(0)))),'exchange_count':len(exchanges),'last_visit':max(activity) if activity else None,'preferred_payment':max(methods,key=methods.get) if sales_rows else None}

@app.get(prefix+'/admin/customers')
def customers(q:str='',user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    term=q.strip().lower()
    if len(term)>100:raise HTTPException(422,'Search is too long.')
    mobiles={x for x in db.scalars(select(POSCustomer.mobile)).all() if x}
    mobiles.update(x for x in db.scalars(select(User.phone).where(User.role=='customer',User.phone!=None)).all() if x)
    results=[customer_summary(db,mobile) for mobile in mobiles]
    if term:results=[x for x in results if term in x['name'].lower() or term in x['mobile'].lower() or term in x['public_code'].lower() or term in (x['email'] or '').lower()]
    return sorted(results,key=lambda x:x['last_visit'] or now()-timedelta(days=36500),reverse=True)[:500]

@app.get(prefix+'/admin/customers/{mobile}')
def customer_detail(mobile:str,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    customer,account=customer_identity(db,mobile)
    result=customer_summary(db,mobile)
    sales_rows=db.scalars(select(Sale).where(Sale.customer_mobile==mobile).order_by(Sale.id.desc()).limit(200)).all()
    sale_ids=[sale.id for sale in sales_rows]
    exchanges=db.scalars(select(ReturnExchange).where(ReturnExchange.sale_id.in_(sale_ids)).order_by(ReturnExchange.id.desc()).limit(200)).all() if sale_ids else []
    orders_rows=db.scalars(select(Order).where(Order.user_id==account.id).order_by(Order.id.desc()).limit(200)).all() if account else []
    return {**result,'sales':[sale_view(db,sale) for sale in sales_rows],'orders':[order_view(db,order,user) for order in orders_rows],'returns_exchanges':[return_exchange_view(db,exchange) for exchange in exchanges]}

@app.get(prefix+'/admin/settings/reservations')
def reservation_settings(user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    return {'reservation_hours':reservation_hours(db)}

@app.put(prefix+'/admin/settings/reservations')
def reservation_settings_update(data:ReservationSettingsIn,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    setting=db.get(SystemSetting,'reservation_hours')
    if setting:
        setting.value=str(data.reservation_hours);setting.updated_by=user.id;setting.updated_at=now()
    else:
        db.add(SystemSetting(key='reservation_hours',value=str(data.reservation_hours),updated_by=user.id))
    audit(db,user,'settings.reservation.update','reservation_hours',hours=data.reservation_hours)
    return {'reservation_hours':data.reservation_hours}

@app.post(prefix+'/admin/users/{ident}/toggle')
def staff_toggle(ident:int,user:User=UserDep,db:DBSession=DB):
    require(user,('admin',));u=get_or_404(db,User,ident)
    if u.role=='admin':raise HTTPException(409,'Administrator accounts cannot be disabled here.')
    u.active=not u.active;audit(db,user,'user.active',ident,active=u.active)
    return {'ok':True}

@app.get(prefix+'/dashboard')
def dashboard(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    require(user,('admin','manager'))
    if user.role!='admin': branch_id=user.branch_id
    sq=select(Sale);oq=select(Order);iq=select(Stock)
    if branch_id:sq=sq.where(Sale.branch_id==branch_id);oq=oq.where(Order.branch_id==branch_id);iq=iq.where(Stock.branch_id==branch_id)
    ss=db.scalars(sq).all();oo=db.scalars(oq).all();stocks=db.scalars(iq).all()
    gross=sum((s.total-s.refunded for s in ss),Decimal(0))+sum((o.total for o in oo if o.status=='completed'),Decimal(0))
    trend=[]
    for offset in range(6,-1,-1):
        day=(now()+timedelta(hours=5,minutes=30)-timedelta(days=offset)).date()
        pos=sum((s.total-s.refunded for s in ss if (s.created_at+timedelta(hours=5,minutes=30)).date()==day),Decimal(0))
        online=sum((o.total for o in oo if o.status=='completed' and (o.created_at+timedelta(hours=5,minutes=30)).date()==day),Decimal(0))
        trend.append({'day':day.isoformat(),'pos':pos,'online':online})
    return {'net_sales':gross,'pos_sales':sum((s.total-s.refunded for s in ss),Decimal(0)),'online_sales':sum((o.total for o in oo if o.status=='completed'),Decimal(0)),'pending_orders':sum(o.status not in ('completed','cancelled') for o in oo),'low_stock':sum(available(s)<=s.reorder for s in stocks),'trend':trend,'sales_count':len(ss),'orders_count':len(oo)}

@app.get(prefix+'/reports/sales.csv')
def report(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    require(user,('admin','manager'))
    if user.role!='admin':branch_id=user.branch_id
    out=io.StringIO();writer=csv.writer(out);writer.writerow(['channel','number','branch','date_utc','gross','refund','net','status'])
    for cls,channel in ((Sale,'POS'),(Order,'Online')):
        q=select(cls)
        if branch_id:q=q.where(cls.branch_id==branch_id)
        for x in db.scalars(q.order_by(cls.id)).all():
            refund=x.refunded if cls==Sale else 0
            net=x.total-refund if cls==Sale or x.status=='completed' else 0
            writer.writerow([channel,x.id,x.branch_id,x.created_at.isoformat(),x.total,refund,net,'completed' if cls==Sale else x.status])
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="chinnu-sales.csv"'})

@app.get(prefix+'/admin/audit')
def audit_list(user:User=UserDep,db:DBSession=DB):
    require(user,('admin',))
    return [row(x) for x in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(200)).all()]

@app.get(prefix+'/shifts')
def shifts(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    if branch_id is None: require(user,('admin',))
    else: scope(user,branch_id,('admin','manager','cashier'))
    q=select(Shift)
    if branch_id is not None:q=q.where(Shift.branch_id==branch_id)
    if user.role=='cashier':q=q.where(Shift.actor_id==user.id)
    result=[]
    for s in db.scalars(q.order_by(Shift.id.desc()).limit(100)).all():
        totals={method:db.scalar(select(func.coalesce(func.sum(SalePayment.amount),0)).join(Sale,Sale.id==SalePayment.sale_id).where(Sale.shift_id==s.id,SalePayment.method==method))+db.scalar(select(func.coalesce(func.sum(ReturnExchange.amount_due-ReturnExchange.refund_due),0)).where(ReturnExchange.shift_id==s.id,ReturnExchange.settlement_method==method)) for method in ('cash','card','upi')}
        cashier=db.get(User,s.actor_id).name
        system=f"{s.system_info or 'System not recorded'} · IP {s.client_ip or 'not recorded'}"
        result.append({**row(s),'branch_name':db.get(Branch,s.branch_id).name,'cashier':f'{cashier} — {system}','current_expected':format(money(s.opening_cash+totals['cash']),'.2f'),'current_expected_card':format(money(totals['card']),'.2f'),'current_expected_upi':format(money(totals['upi']),'.2f')})
    return result

@app.post(prefix+'/shifts/open')
def shift_open(data:ShiftOpenIn,request:Request,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    scope(user,data.branch_id,('admin','manager','cashier'))
    def apply():
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':10_000_000+user.id})
        if db.scalar(select(Shift).where(Shift.actor_id==user.id,Shift.closed_at==None)):
            raise HTTPException(409,'Close your existing cashier shift before opening another.')
        client_ip=request.headers.get('x-real-ip') or (request.client.host if request.client else None)
        system_info=system_label(request.headers.get('user-agent'))
        s=Shift(actor_id=user.id,branch_id=data.branch_id,opening_cash=data.cash,client_ip=client_ip,system_info=system_info);db.add(s);db.flush();audit(db,user,'shift.open',s.id,cash=str(data.cash),client_ip=client_ip,system_info=system_info)
        return {'id':s.id}
    return idempotent(db,user,'shift.open',idempotency_key,data.model_dump(mode='json'),apply)

@app.post(prefix+'/shifts/{ident}/close')
def shift_close(ident:int,data:ShiftCloseIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    s=get_or_404(db,Shift,ident,True);scope(user,s.branch_id,('manager','cashier'))
    if s.actor_id!=user.id:raise HTTPException(403,'Only your own shift can be submitted for closure.')
    def apply():
        if s.closure_status!='open':raise HTTPException(409,'This shift has already been submitted for closure.')
        totals={method:db.scalar(select(func.coalesce(func.sum(SalePayment.amount),0)).join(Sale,Sale.id==SalePayment.sale_id).where(Sale.shift_id==s.id,SalePayment.method==method))+db.scalar(select(func.coalesce(func.sum(ReturnExchange.amount_due-ReturnExchange.refund_due),0)).where(ReturnExchange.shift_id==s.id,ReturnExchange.settlement_method==method)) for method in ('cash','card','upi')}
        s.expected_cash=s.opening_cash+totals['cash'];s.counted_cash=data.cash;s.variance=data.cash-s.expected_cash
        s.expected_card=totals['card'];s.counted_card=data.card;s.card_variance=data.card-s.expected_card
        s.expected_upi=totals['upi'];s.counted_upi=data.upi;s.upi_variance=data.upi-s.expected_upi
        shortage=any(value<0 for value in (s.variance,s.card_variance,s.upi_variance))
        reason=(data.shortage_reason or '').strip()
        if shortage and len(reason)<3:raise HTTPException(422,'Enter a reason for the payment shortage.')
        s.shortage_reason=reason or None;s.closure_requested_at=now();s.closed_at=now();s.closure_status='pending'
        audit(db,user,'shift.close_requested',s.id,counted_cash=str(data.cash),cash_variance=str(s.variance),counted_card=str(data.card),card_variance=str(s.card_variance),counted_upi=str(data.upi),upi_variance=str(s.upi_variance),shortage_reason=s.shortage_reason)
        return {'id':s.id,'closure_status':s.closure_status,'variance':format(money(s.variance),'.2f'),'card_variance':format(money(s.card_variance),'.2f'),'upi_variance':format(money(s.upi_variance),'.2f')}
    return idempotent(db,user,f'shift.close.{ident}',idempotency_key,data.model_dump(mode='json'),apply)

@app.post(prefix+'/shifts/{ident}/approve-close')
def shift_approve_close(ident:int,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    s=get_or_404(db,Shift,ident,True);scope(user,s.branch_id,('manager',))
    def apply():
        if s.closure_status!='pending':raise HTTPException(409,'Only a pending shift closure can be approved.')
        s.closure_status='approved';s.approved_at=now();s.approved_by=user.id
        audit(db,user,'shift.close_approved',s.id,cash_variance=str(s.variance),card_variance=str(s.card_variance),upi_variance=str(s.upi_variance),shortage_reason=s.shortage_reason)
        return {'id':s.id,'closure_status':s.closure_status}
    return idempotent(db,user,f'shift.approve_close.{ident}',idempotency_key,{},apply)

@app.get(prefix+'/stock-counts')
def count_list(branch_id:int|None=None,user:User=UserDep,db:DBSession=DB):
    if branch_id is None: require(user,('admin',))
    else: scope(user,branch_id)
    statement=select(CountRequest)
    if branch_id is not None:statement=statement.where(CountRequest.branch_id==branch_id)
    return [{**row(c),'branch_name':db.get(Branch,c.branch_id).name,'name':db.get(Variant,c.variant_id).label,'sku':db.get(Variant,c.variant_id).sku} for c in db.scalars(statement.order_by(CountRequest.id.desc()).limit(100)).all()]

@app.post(prefix+'/stock-counts')
def count_create(data:CountIn,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    scope(user,data.branch_id,('admin','manager','inventory'));stock_quantity(db,data.variant_id,data.counted_quantity)
    def apply():
        s=lock_stock(db,data.branch_id,[data.variant_id])[data.variant_id]
        c=CountRequest(**data.model_dump(),system_quantity=s.on_hand,actor_id=user.id)
        db.add(c);db.flush();audit(db,user,'count.submit',c.id)
        return {'id':c.id}
    return idempotent(db,user,'count.create',idempotency_key,data.model_dump(mode='json'),apply)

@app.post(prefix+'/stock-counts/{ident}/approve')
def count_approve(ident:int,user:User=UserDep,db:DBSession=DB,idempotency_key:str|None=Header(default=None)):
    c=get_or_404(db,CountRequest,ident,True);scope(user,c.branch_id,('admin','manager'))
    def apply():
        if c.actor_id==user.id:raise HTTPException(403,'Another authorised manager must approve your count.')
        if c.status!='pending':raise HTTPException(409,'This count is no longer pending.')
        s=lock_stock(db,c.branch_id,[c.variant_id])[c.variant_id]
        if s.on_hand!=c.system_quantity:raise HTTPException(409,'Stock moved since this count. Reject it and submit a fresh count.')
        if c.counted_quantity<s.reserved+s.damaged:raise HTTPException(409,'Count cannot consume reserved or damaged stock. Resolve reservations first.')
        delta=c.counted_quantity-s.on_hand;s.on_hand=c.counted_quantity;c.status='approved';c.approver_id=user.id
        db.add(Movement(branch_id=c.branch_id,variant_id=c.variant_id,delta=delta,kind='count_adjustment',reference=f'COUNT-{ident}',reason=c.reason,actor_id=user.id))
        audit(db,user,'count.approve',ident,delta=str(delta))
        return {'ok':True}
    return idempotent(db,user,f'count.approve.{ident}',idempotency_key,{},apply)

@app.post(prefix+'/stock-counts/{ident}/reject')
def count_reject(ident:int,user:User=UserDep,db:DBSession=DB):
    c=get_or_404(db,CountRequest,ident,True);scope(user,c.branch_id,('admin','manager'))
    if c.status!='pending':raise HTTPException(409,'This count is no longer pending.')
    c.status='rejected';c.approver_id=user.id;audit(db,user,'count.reject',ident)
    return {'ok':True}

