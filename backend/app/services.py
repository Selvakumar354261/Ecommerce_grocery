import hashlib
import json
import math
import secrets
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import and_, or_, select, text
from .models import *

def money(x): return Decimal(x).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
def reservation_hours(db):
    setting=db.get(SystemSetting,'reservation_hours')
    try:return max(1,min(168,int(setting.value))) if setting else 1
    except (TypeError,ValueError):return 1
def audit(db, user, action, reference, **details):
    db.add(Audit(actor_id=user.id if user else None, action=action, reference=str(reference), details=details))

def get_or_404(db, cls, ident, lock=False):
    statement = select(cls).where(cls.id==ident)
    if lock: statement = statement.with_for_update().execution_options(populate_existing=True)
    obj = db.scalar(statement)
    if not obj: raise HTTPException(404, f'{cls.__name__} was not found.')
    return obj

def available(s): return s.on_hand-s.reserved-s.damaged

def stock_quantity(db,variant_id,qty):
    v=get_or_404(db,Variant,variant_id)
    if v.unit in ('pack','piece') and qty != qty.to_integral_value():
        raise HTTPException(422,'Pack and piece stock changes require whole quantities.')

def lock_stock(db, branch, ids):
    result = db.scalars(select(Stock).where(Stock.branch_id==branch,Stock.variant_id.in_(sorted(ids))).order_by(Stock.variant_id).with_for_update().execution_options(populate_existing=True)).all()
    mapping = {s.variant_id:s for s in result}
    if len(mapping) != len(ids): raise HTTPException(409,'Some items are not stocked at this branch.')
    return mapping

def lines(db, items):
    result=[]
    for line in items:
        v=get_or_404(db,Variant,line.variant_id)
        p=get_or_404(db,Product,v.product_id)
        if not v.active or not p.active: raise HTTPException(409,f'{p.name} is no longer available.')
        q=line.quantity
        if q<v.min_qty or q>v.max_qty or (q-v.min_qty)%v.step != 0:
            raise HTTPException(422,f'{p.name}: choose {v.min_qty} to {v.max_qty} {v.unit}, in steps of {v.step}.')
        result.append(dict(variant_id=v.id,name=f'{p.name} · {v.label}',unit=v.unit,quantity=q,price=v.price,line_total=money(v.price*q)))
    return result

def distance(lat,lon,blat,blon):
    a,b,c,d=map(math.radians,[float(lat),float(lon),float(blat),float(blon)])
    h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 6371*2*math.asin(min(1,math.sqrt(h)))

def distance_delivery_fee(branch,km):
    km=Decimal(str(km))
    if km>branch.radius_km:return Decimal('0.00')  # Manager quotes outside coverage.
    for slab in branch.delivery_slabs or []:
        if km<=Decimal(str(slab['up_to_km'])):return money(Decimal(str(slab['fee'])))
    if branch.delivery_slabs:raise HTTPException(409,'Branch delivery pricing is incomplete. Contact the branch.')
    return money(branch.delivery_fee)

def eligibility(db, data):
    checked=lines(db,data.items)
    result=[]
    for b in db.scalars(select(Branch).where(Branch.active==True,Branch.accepting_orders==True)).all():
        km=distance(data.latitude,data.longitude,b.latitude,b.longitude)
        stock={s.variant_id:s for s in db.scalars(select(Stock).where(Stock.branch_id==b.id)).all()}
        missing=[x['name'] for x in checked if x['variant_id'] not in stock or available(stock[x['variant_id']])<x['quantity']]
        covered=data.method=='pickup' or km<=b.radius_km
        result.append(dict(id=b.id,name=b.name,address=b.address,hours=b.hours,distance_km=round(km,2),eligible=not missing,missing=missing,covered=covered,requires_approval=not covered,delivery_fee=str(distance_delivery_fee(b,km) if data.method=='delivery' else 0),recommended=False))
    result.sort(key=lambda x:(not x['eligible'],x['requires_approval'],x['distance_km']))
    subtotal=sum((line['line_total'] for line in checked),Decimal(0))
    for option in result:
        option['subtotal']=str(money(subtotal))
        option['total']=str(money(subtotal+Decimal(option['delivery_fee'])))
    first=next((x for x in result if x['eligible']),None)
    if first: first['recommended']=True
    return result

def idempotent(db,user,operation,key,payload,fn):
    if not key or len(key)>100: raise HTTPException(400,'A valid Idempotency-Key is required.')
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    lockkey=int.from_bytes(hashlib.sha256(f'{user.id}:{operation}:{key}'.encode()).digest()[:8],'big',signed=True)
    db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':lockkey})
    existing=db.scalar(select(Idempotency).where(Idempotency.actor_id==user.id,Idempotency.operation==operation,Idempotency.key==key))
    if existing:
        if existing.fingerprint!=fingerprint: raise HTTPException(409,'This retry key belongs to a different request.')
        return existing.response
    response=json.loads(json.dumps(fn(),default=str))
    db.flush()
    db.add(Idempotency(actor_id=user.id,operation=operation,key=key,fingerprint=fingerprint,response=response))
    return response

def create_order(db,user,data):
    if data.method=='delivery' and len(data.address.strip())<8: raise HTTPException(422,'Enter a complete delivery address.')
    b=get_or_404(db,Branch,data.branch_id,True)
    if not b.active or not b.accepting_orders: raise HTTPException(409,'This branch is not accepting orders.')
    delivery_distance=Decimal(str(distance(data.latitude,data.longitude,b.latitude,b.longitude))) if data.method=='delivery' else None
    requires_approval=data.method=='delivery' and delivery_distance>b.radius_km
    checked=lines(db,data.items)
    stock=lock_stock(db,b.id,[x['variant_id'] for x in checked])
    for x in checked:
        s=stock[x['variant_id']]
        if available(s)<x['quantity']: raise HTTPException(409,f"{x['name']} has insufficient stock. Refresh branch options.")
        s.reserved+=x['quantity']
    subtotal=sum((x['line_total'] for x in checked),Decimal(0))
    if data.expected_subtotal is not None and data.expected_subtotal!=subtotal:
        raise HTTPException(409,'Product prices changed. Refresh the catalogue and review your total.')
    fee=Decimal(0) if requires_approval else (distance_delivery_fee(b,delivery_distance) if data.method=='delivery' else Decimal(0))
    placed_at=now();status='approval_pending' if requires_approval else 'placed'
    order=Order(user_id=user.id,branch_id=b.id,method=data.method,address=data.address,latitude=Decimal(str(data.latitude)),longitude=Decimal(str(data.longitude)),phone=data.phone,status=status,subtotal=subtotal,delivery_fee=fee,total=subtotal+fee,pickup_code=str(secrets.randbelow(900000)+100000),coverage_approval_required=requires_approval,delivery_distance_km=delivery_distance,approval_expires_at=placed_at+timedelta(hours=24) if requires_approval else None,expires_at=None if requires_approval else placed_at+timedelta(hours=reservation_hours(db)))
    db.add(order);db.flush()
    for x in checked: db.add(OrderItem(order_id=order.id,**x))
    note='Order placed outside normal delivery coverage; awaiting manager approval within 24 hours.' if requires_approval else 'Stock reserved; awaiting branch confirmation.'
    db.add(OrderEvent(order_id=order.id,status=status,actor_id=user.id,note=note))
    audit(db,user,'order.create',order.id)
    return {'id':order.id,'number':f'ORD-{order.id:06d}','total':str(order.total),'status':status,'requires_approval':requires_approval}

def release(db,order,user=None,note='Cancelled',event_status='cancelled'):
    if order.reserved_active:
        items=db.scalars(select(OrderItem).where(OrderItem.order_id==order.id)).all()
        stocks=lock_stock(db,order.branch_id,[x.variant_id for x in items])
        for x in items: stocks[x.variant_id].reserved-=x.quantity
        order.reserved_active=False
    order.status='cancelled';order.expires_at=None;order.approval_expires_at=None
    db.add(OrderEvent(order_id=order.id,status=event_status,actor_id=user.id if user else None,note=note))

def transition(db,user,ident,data):
    o=get_or_404(db,Order,ident,True)
    from .security import scope
    if user.role=='customer':
        if o.user_id!=user.id: raise HTTPException(404,'Order not found.')
        if data.action!='cancel' or o.status not in ('placed','approval_pending'): raise HTTPException(409,'Contact the store to change this order.')
    else: scope(user,o.branch_id,('admin','manager'))
    if data.action in ('approve_coverage','reject_coverage'):
        if user.role not in ('admin','manager'):raise HTTPException(403,'A branch manager must review out-of-coverage orders.')
        if o.status!='approval_pending' or not o.coverage_approval_required:raise HTTPException(409,'This order is not awaiting coverage approval.')
        if data.action=='reject_coverage':
            release(db,o,user,data.note.strip(),event_status='rejected')
        else:
            if o.approval_expires_at and o.approval_expires_at<=now():raise HTTPException(409,'The 24-hour approval window has expired.')
            o.delivery_fee=money(data.delivery_charge);o.total=money(o.subtotal+o.delivery_fee);o.estimated_delivery_days=data.estimated_delivery_days
            o.status='placed';o.coverage_approved_at=now();o.coverage_approved_by=user.id;o.approval_expires_at=None;o.expires_at=now()+timedelta(hours=reservation_hours(db))
            note=data.note or f'Out-of-coverage delivery approved. Delivery charge: {o.delivery_fee}; estimated delivery: {o.estimated_delivery_days} day(s).'
            db.add(OrderEvent(order_id=o.id,status='placed',actor_id=user.id,note=note))
    elif data.action=='reject':
        if user.role=='customer':raise HTTPException(403,'Customers cancel orders; only the store can reject an order.')
        if o.payment_status=='paid':raise HTTPException(409,'Cash has been collected. Use the supervised refund process instead.')
        if o.status not in ('approval_pending','placed','confirmed','preparing','ready'):raise HTTPException(409,'This order can no longer be rejected.')
        release(db,o,user,data.note.strip(),event_status='rejected')
    elif data.action=='cancel':
        if user.role!='customer':raise HTTPException(422,'Store staff must reject an order and provide a reason.')
        if o.payment_status=='paid': raise HTTPException(409,'Cash has been collected. Contact the manager for a supervised refund; cancellation is blocked.')
        if o.status not in ('approval_pending','placed','confirmed','preparing','ready'): raise HTTPException(409,'This order can no longer be cancelled.')
        release(db,o,user,data.note or 'Order cancelled at the customer’s request.')
    else:
        mapping={'confirm':('placed','confirmed'),'prepare':('confirmed','preparing'),'ready':('preparing','ready'),'dispatch':('ready','dispatched'),'deliver':('dispatched','completed'),'collect':('ready','completed')}
        before,after=mapping[data.action]
        if o.status!=before: raise HTTPException(409,f'This action requires order status {before}.')
        if data.action in ('dispatch','deliver') and o.method!='delivery': raise HTTPException(409,'This is a pickup order.')
        if data.action=='collect':
            if o.method!='pickup' or not secrets.compare_digest(o.pickup_code,data.pickup_code): raise HTTPException(422,'Enter the correct pickup code.')
        if data.action=='confirm':
            if o.expires_at and o.expires_at<=now():
                raise HTTPException(409,'Reservation has expired. It will be released by the worker.')
            o.expires_at=None
        if data.action in ('dispatch','collect'):
            if not o.reserved_active: raise HTTPException(409,'Reservation is no longer active.')
            items=db.scalars(select(OrderItem).where(OrderItem.order_id==o.id)).all()
            stocks=lock_stock(db,o.branch_id,[x.variant_id for x in items])
            for x in items:
                s=stocks[x.variant_id];s.on_hand-=x.quantity;s.reserved-=x.quantity
                db.add(Movement(branch_id=o.branch_id,variant_id=x.variant_id,delta=-x.quantity,kind='order_fulfilment',reference=f'ORD-{o.id}',actor_id=user.id))
            o.reserved_active=False
        if after=='completed' and o.payment_status!='paid': raise HTTPException(409,'Record cash collection before completing the order.')
        o.status=after
        db.add(OrderEvent(order_id=o.id,status=after,actor_id=user.id,note=data.note))
    audit(db,user,'order.'+data.action,o.id)
    return {'id':o.id,'status':o.status}

def create_sale(db,user,data):
    shift=db.scalar(select(Shift).where(Shift.actor_id==user.id,Shift.branch_id==data.branch_id,Shift.closed_at==None).with_for_update())
    if not shift:raise HTTPException(409,'Open a cashier shift before completing a sale.')
    checked=lines(db,data.items)
    stock=lock_stock(db,data.branch_id,[x['variant_id'] for x in checked])
    total=sum((x['line_total'] for x in checked),Decimal(0))
    if data.expected_subtotal is not None and total!=data.expected_subtotal:raise HTTPException(409,'Product prices changed. Refresh and review the bill.')
    if data.payment_method=='split':
        if len(data.payments)<2:raise HTTPException(422,'Split payment requires at least two payment methods.')
        methods=[payment.method for payment in data.payments]
        if len(set(methods))!=len(methods):raise HTTPException(422,'Each split payment method can be used only once.')
        allocations={payment.method:money(payment.amount) for payment in data.payments}
        if sum(allocations.values(),Decimal(0))!=total:raise HTTPException(422,'Split payment amounts must exactly equal the bill total.')
    else:
        if data.payments:raise HTTPException(422,'Payment breakdown is only accepted for split payments.')
        allocations={data.payment_method:total}
    cash_amount=allocations.get('cash',Decimal(0))
    if data.payment_method=='split':
        if data.amount_tendered is not None and data.amount_tendered!=cash_amount:raise HTTPException(422,'For split payments, cash collected must equal the cash portion; no change is calculated.')
        amount_tendered=money(cash_amount) if cash_amount else None;change_due=Decimal(0)
    elif cash_amount:
        if data.amount_tendered is None:raise HTTPException(422,'Enter the actual cash received from the customer.')
        if data.amount_tendered<cash_amount:raise HTTPException(422,'Cash received cannot be less than the cash portion.')
        amount_tendered=money(data.amount_tendered);change_due=money(amount_tendered-cash_amount)
    else:
        if data.amount_tendered is not None:raise HTTPException(422,'Cash received is only used when a cash portion exists.')
        amount_tendered=None;change_due=Decimal(0)
    customer_lock=int.from_bytes(hashlib.sha256(('pos-customer:'+data.customer_mobile).encode()).digest()[:8],'big',signed=True)
    db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':customer_lock})
    customer=db.scalar(select(POSCustomer).where(POSCustomer.mobile==data.customer_mobile))
    account=db.scalar(select(User).where(User.role=='customer',User.phone==data.customer_mobile))
    if not customer:
        name=account.name.strip().upper() if account else (data.customer_name or '').strip().upper()
        if len(name)<2:raise HTTPException(422,'Enter the customer name for a new mobile number.')
        customer=POSCustomer(mobile=data.customer_mobile,name=name,public_code='CUS-'+secrets.token_hex(5).upper());db.add(customer);db.flush()
    elif account and customer.name!=account.name.strip().upper():
        customer.name=account.name.strip().upper();customer.updated_at=now()
    sale=Sale(branch_id=data.branch_id,actor_id=user.id,shift_id=shift.id,total=total,payment_method=data.payment_method,amount_tendered=amount_tendered,change_due=change_due,customer_id=customer.id,customer_name=customer.name,customer_mobile=customer.mobile,customer_code=customer.public_code)
    db.add(sale);db.flush()
    for method,payment_amount in allocations.items():db.add(SalePayment(sale_id=sale.id,method=method,amount=payment_amount))
    for x in checked:
        s=stock[x['variant_id']]
        if available(s)<x['quantity']: raise HTTPException(409,f"Only {available(s)} available for {x['name']}.")
        s.on_hand-=x['quantity']
        db.add(SaleItem(sale_id=sale.id,**x))
        db.add(Movement(branch_id=data.branch_id,variant_id=x['variant_id'],delta=-x['quantity'],kind='pos_sale',reference=f'POS-{sale.id}',actor_id=user.id))
    audit(db,user,'sale.create',sale.id)
    return {'id':sale.id,'number':f'POS-{sale.id:06d}','total':str(total),'payment_method':sale.payment_method,'payments':[{'method':method,'amount':str(payment_amount)} for method,payment_amount in allocations.items()],'change_due':str(change_due)}

def expire_reservations(db):
    expired=db.scalars(select(Order).where(or_(and_(Order.status=='placed',Order.expires_at<=now()),and_(Order.status=='approval_pending',Order.approval_expires_at<=now())),Order.reserved_active==True).order_by(Order.id).with_for_update(skip_locked=True).limit(100)).all()
    for order in expired:
        note='We were unable to confirm your order due to operational or technical reasons. Please contact the branch for assistance or place a new order.' if order.status=='approval_pending' else 'Expired before branch confirmation. Please place a new order.'
        release(db,order,note=note,event_status='rejected' if order.status=='approval_pending' else 'cancelled')
        audit(db,None,'order.expired',order.id)
    return len(expired)

