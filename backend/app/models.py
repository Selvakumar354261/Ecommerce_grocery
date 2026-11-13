from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now():
    return datetime.now(timezone.utc)

class Branch(Base):
    __tablename__ = 'branches'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(500))
    latitude: Mapped[float] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float] = mapped_column(Numeric(10, 7))
    radius_km: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=10)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=30)
    delivery_slabs: Mapped[list] = mapped_column(JSON, default=list, server_default='[]')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    accepting_orders: Mapped[bool] = mapped_column(Boolean, default=True)
    hours: Mapped[str] = mapped_column(String(120), default='09:00–21:00')

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(180), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default='customer')
    branch_id: Mapped[int | None] = mapped_column(ForeignKey('branches.id'))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class CustomerAddress(Base):
    __tablename__ = 'customer_addresses'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    label: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(10))
    latitude: Mapped[Decimal] = mapped_column(Numeric(10,7))
    longitude: Mapped[Decimal] = mapped_column(Numeric(10,7))
    __table_args__ = (CheckConstraint('latitude >= -90 AND latitude <= 90'), CheckConstraint('longitude >= -180 AND longitude <= 180'))

class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    csrf: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class LoginAttempt(Base):
    __tablename__ = 'login_attempts'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    window: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class MobileOTP(Base):
    __tablename__ = 'mobile_otps'
    phone: Mapped[str] = mapped_column(String(20), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    attempts: Mapped[int] = mapped_column(default=0)

class SystemSetting(Base):
    __tablename__ = 'system_settings'
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Product(Base):
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(String(1000), default='')
    tone: Mapped[str] = mapped_column(String(20), default='sage')
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Variant(Base):
    __tablename__ = 'variants'
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    sku: Mapped[str] = mapped_column(String(60), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(20))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    min_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=1)
    step: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=1)
    max_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint('price > 0 AND step > 0 AND min_qty > 0 AND max_qty >= min_qty'),)

class Stock(Base):
    __tablename__ = 'stock'
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey('branches.id'), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey('variants.id'), index=True)
    on_hand: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    reserved: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    damaged: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    reorder: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=5)
    __table_args__ = (UniqueConstraint('branch_id', 'variant_id'), CheckConstraint('on_hand >= 0 AND reserved >= 0 AND damaged >= 0 AND on_hand >= reserved + damaged'))

class Movement(Base):
    __tablename__ = 'movements'
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey('branches.id'), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey('variants.id'))
    delta: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    kind: Mapped[str] = mapped_column(String(40))
    reference: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(500), default='')
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey('branches.id'), index=True)
    method: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(500), default='')
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    phone: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default='placed')
    payment_status: Mapped[str] = mapped_column(String(20), default='unpaid')
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    pickup_code: Mapped[str] = mapped_column(String(8))
    reserved_active: Mapped[bool] = mapped_column(Boolean, default=True)
    coverage_approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    approval_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    estimated_delivery_days: Mapped[int | None] = mapped_column(Integer)
    assigned_delivery_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'),index=True)
    delivery_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    driver_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    driver_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    driver_location_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

class OrderCollection(Base):
    __tablename__ = 'order_collections'
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    payment_method: Mapped[str] = mapped_column(String(20))
    payments: Mapped[list] = mapped_column(JSON)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_tendered: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    change_due: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class OrderItem(Base):
    __tablename__ = 'order_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey('variants.id'))
    name: Mapped[str] = mapped_column(String(260))
    unit: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

class OrderEvent(Base):
    __tablename__ = 'order_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), index=True)
    status: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(String(500), default='')
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class POSCustomer(Base):
    __tablename__ = 'pos_customers'
    id: Mapped[int] = mapped_column(primary_key=True)
    mobile: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    public_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Sale(Base):
    __tablename__ = 'sales'
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey('branches.id'), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    shift_id: Mapped[int] = mapped_column(ForeignKey('shifts.id'), index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    refunded: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    payment_method: Mapped[str] = mapped_column(String(20), default='cash')
    amount_tendered: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    change_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey('pos_customers.id'), index=True)
    customer_name: Mapped[str] = mapped_column(String(100))
    customer_mobile: Mapped[str] = mapped_column(String(10), index=True)
    customer_code: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

class SaleItem(Base):
    __tablename__ = 'sale_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey('sales.id'), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey('variants.id'))
    name: Mapped[str] = mapped_column(String(260))
    unit: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    returned: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

class SalePayment(Base):
    __tablename__ = 'sale_payments'
    __table_args__ = (UniqueConstraint('sale_id','method',name='uq_sale_payment_method'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey('sales.id',ondelete='CASCADE'),index=True)
    method: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(12,2))

class ReturnExchange(Base):
    __tablename__ = 'return_exchanges'
    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey('sales.id'), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey('branches.id'), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    shift_id: Mapped[int] = mapped_column(ForeignKey('shifts.id'), index=True)
    customer_code: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    returned_items: Mapped[list] = mapped_column(JSON)
    replacement_items: Mapped[list] = mapped_column(JSON)
    return_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    replacement_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_due: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    refund_due: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    settlement_method: Mapped[str] = mapped_column(String(20))
    amount_tendered: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    change_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Transfer(Base):
    __tablename__ = 'transfers'
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey('branches.id'))
    target_id: Mapped[int] = mapped_column(ForeignKey('branches.id'))
    variant_id: Mapped[int] = mapped_column(ForeignKey('variants.id'))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    received: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    status: Mapped[str] = mapped_column(String(30), default='in_transit')
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Supplier(Base):
    __tablename__ = 'suppliers'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    phone: Mapped[str] = mapped_column(String(30), default='')
    address: Mapped[str] = mapped_column(String(500), default='')

class Purchase(Base):
    __tablename__ = 'purchases'
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey('suppliers.id'))
    branch_id: Mapped[int] = mapped_column(ForeignKey('branches.id'))
    variant_id: Mapped[int] = mapped_column(ForeignKey('variants.id'))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    received: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(30), default='ordered')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(80))
    reference: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Idempotency(Base):
    __tablename__ = 'idempotency'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    operation: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('actor_id','operation','key'),)

class Shift(Base):
    __tablename__ = 'shifts'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey('branches.id'), index=True)
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    variance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    counted_card: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    expected_card: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    card_variance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    counted_upi: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    expected_upi: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    upi_variance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closure_status: Mapped[str] = mapped_column(String(20),default='open')
    closure_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shortage_reason: Mapped[str | None] = mapped_column(String(500))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    client_ip: Mapped[str | None] = mapped_column(String(45))
    system_info: Mapped[str | None] = mapped_column(String(200))

class CountRequest(Base):
    __tablename__ = 'count_requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey('branches.id'))
    variant_id: Mapped[int] = mapped_column(ForeignKey('variants.id'))
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    approver_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    counted_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

