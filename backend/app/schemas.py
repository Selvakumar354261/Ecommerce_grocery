from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator

Qty = Decimal

class LoginIn(BaseModel):
    email: str = Field(min_length=3,max_length=180)
    password: str = Field(min_length=1,max_length=128)

class RegisterIn(LoginIn):
    name: str = Field(min_length=2,max_length=100)
    password: str = Field(min_length=10,max_length=128)

class OTPRequestIn(BaseModel):
    phone: str = Field(pattern=r'^[6-9][0-9]{9}$')

class OTPVerifyIn(OTPRequestIn):
    otp: str = Field(pattern=r'^[0-9]{6}$')
    name: str | None = Field(default=None,max_length=100)
    email: str | None = Field(default=None,max_length=180)

class LineIn(BaseModel):
    variant_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0,le=100000,max_digits=14,decimal_places=3)

class CartIn(BaseModel):
    items: list[LineIn] = Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def unique(self):
        if len({x.variant_id for x in self.items}) != len(self.items):
            raise ValueError('Combine quantities for the same variant into one line.')
        return self

class EligibilityIn(CartIn):
    method: Literal['delivery','pickup']
    latitude: float = Field(ge=-90,le=90)
    longitude: float = Field(ge=-180,le=180)

class OrderIn(EligibilityIn):
    branch_id: int = Field(gt=0)
    address: str = Field(default='',max_length=500)
    phone: str = Field(pattern=r'^\+?[0-9 ()-]{8,20}$')
    expected_subtotal: Decimal | None = Field(default=None,ge=0,max_digits=12,decimal_places=2)

class TransitionIn(BaseModel):
    action: Literal['approve_coverage','reject_coverage','reject','confirm','prepare','ready','dispatch','deliver','collect','cancel']
    pickup_code: str = Field(default='',max_length=6,pattern=r'^(?:|[0-9]{6})$')
    note: str = Field(default='',max_length=500)
    delivery_charge: Decimal | None = Field(default=None,ge=0,le=100000,max_digits=12,decimal_places=2)
    estimated_delivery_days: int | None = Field(default=None,ge=1,le=60)
    @model_validator(mode='after')
    def approval_details(self):
        if self.action=='approve_coverage' and (self.delivery_charge is None or self.estimated_delivery_days is None):
            raise ValueError('Delivery charge and estimated delivery days are required for approval.')
        if self.action in ('reject_coverage','reject') and len(self.note.strip())<3:
            raise ValueError('Enter a rejection reason for the customer.')
        if self.action!='approve_coverage' and (self.delivery_charge is not None or self.estimated_delivery_days is not None):
            raise ValueError('Delivery details are only accepted during coverage approval.')
        return self

class SalePaymentIn(BaseModel):
    method: Literal['cash','card','upi']
    amount: Decimal = Field(gt=0,le=10000000,max_digits=12,decimal_places=2)

class SaleIn(CartIn):
    branch_id: int = Field(gt=0)
    customer_mobile: str = Field(pattern=r'^[6-9][0-9]{9}$')
    customer_name: str | None = Field(default=None,min_length=2,max_length=100)
    payment_method: Literal['cash','card','upi','split'] = 'cash'
    payments: list[SalePaymentIn] = Field(default_factory=list,max_length=3)
    amount_tendered: Decimal | None = Field(default=None,ge=0,le=10000000,max_digits=12,decimal_places=2)
    expected_subtotal: Decimal | None = Field(default=None,ge=0,max_digits=12,decimal_places=2)

class StockIn(BaseModel):
    branch_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0,le=100000,max_digits=14,decimal_places=3)
    reason: str = Field(min_length=3,max_length=500)
    kind: Literal['receive','damage','adjust_up','adjust_down'] = 'receive'

class VariantIn(BaseModel):
    sku: str = Field(min_length=2,max_length=60)
    label: str = Field(min_length=1,max_length=80)
    unit: Literal['pack','kg','litre','piece']
    price: Decimal = Field(gt=0,le=1000000,max_digits=12,decimal_places=2)
    min_qty: Decimal = Field(default=1,gt=0,max_digits=14,decimal_places=3)
    step: Decimal = Field(default=1,gt=0,max_digits=14,decimal_places=3)
    max_qty: Decimal = Field(default=100,gt=0,max_digits=14,decimal_places=3)
    @model_validator(mode='after')
    def limits(self):
        if self.max_qty < self.min_qty: raise ValueError('Maximum must be at least minimum.')
        if self.unit in ('pack','piece') and any(v != v.to_integral_value() for v in (self.min_qty,self.step,self.max_qty)):
            raise ValueError('Pack and piece quantities must be whole numbers.')
        return self

class ProductIn(BaseModel):
    name: str = Field(min_length=2,max_length=180)
    category: str = Field(min_length=2,max_length=80)
    description: str = Field(default='',max_length=1000)
    tone: Literal['sage','gold','rose','clay'] = 'sage'
    variants: list[VariantIn] = Field(min_length=1,max_length=20)

class PriceIn(BaseModel):
    price: Decimal = Field(gt=0,le=1000000,max_digits=12,decimal_places=2)

class BranchIn(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    address: str = Field(min_length=3,max_length=500)
    latitude: float = Field(ge=-90,le=90)
    longitude: float = Field(ge=-180,le=180)
    radius_km: Decimal = Field(gt=0,le=500)
    delivery_fee: Decimal = Field(ge=0,le=10000)
    hours: str = Field(default='09:00–21:00',max_length=120)
    accepting_orders: bool = True
    active: bool = True

class StaffIn(RegisterIn):
    role: Literal['manager','cashier','inventory']
    branch_id: int = Field(gt=0)

class StaffUpdateIn(BaseModel):
    name: str = Field(min_length=2,max_length=100)
    email: str = Field(min_length=3,max_length=180)
    role: Literal['manager','cashier','inventory']
    branch_id: int = Field(gt=0)
    password: str | None = Field(default=None,min_length=10,max_length=128)

class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1,max_length=128)
    new_password: str = Field(min_length=10,max_length=128)

class TransferIn(BaseModel):
    source_id: int = Field(gt=0)
    target_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0,le=100000,max_digits=14,decimal_places=3)

class QuantityIn(BaseModel):
    quantity: Decimal = Field(gt=0,le=100000,max_digits=14,decimal_places=3)

class SupplierIn(BaseModel):
    name: str = Field(min_length=2,max_length=180)
    phone: str = Field(default='',max_length=30)
    address: str = Field(default='',max_length=500)

class PurchaseIn(QuantityIn):
    supplier_id: int = Field(gt=0)
    branch_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)
    unit_cost: Decimal = Field(gt=0,le=1000000,max_digits=12,decimal_places=2)

class PurchaseReceiveIn(QuantityIn):
    unit_cost: Decimal = Field(gt=0,le=1000000,max_digits=12,decimal_places=2)

class ReturnIn(QuantityIn):
    item_id: int = Field(gt=0)
    condition: Literal['sellable','damaged']
    reason: str = Field(min_length=3,max_length=500)

class ReturnLineIn(QuantityIn):
    item_id: int = Field(gt=0)
    condition: Literal['sellable','damaged']

class ReturnExchangeIn(BaseModel):
    returns: list[ReturnLineIn] = Field(min_length=1,max_length=50)
    replacements: list[LineIn] = Field(default_factory=list,max_length=100)
    settlement_method: Literal['cash','card','upi']
    amount_tendered: Decimal | None = Field(default=None,ge=0,le=10000000,max_digits=12,decimal_places=2)
    reason: str = Field(min_length=3,max_length=500)
    @model_validator(mode='after')
    def unique_lines(self):
        if len({x.item_id for x in self.returns})!=len(self.returns):raise ValueError('Combine duplicate return lines.')
        if len({x.variant_id for x in self.replacements})!=len(self.replacements):raise ValueError('Combine duplicate replacement products.')
        return self

class ShiftOpenIn(BaseModel):
    branch_id: int = Field(gt=0)
    cash: Decimal = Field(ge=0,le=10000000,max_digits=12,decimal_places=2)

class ShiftCloseIn(BaseModel):
    branch_id: int = Field(gt=0)
    cash: Decimal = Field(ge=0,le=10000000,max_digits=12,decimal_places=2)
    card: Decimal = Field(ge=0,le=10000000,max_digits=12,decimal_places=2)
    upi: Decimal = Field(ge=0,le=10000000,max_digits=12,decimal_places=2)
    shortage_reason: str | None = Field(default=None,max_length=500)

class CountIn(BaseModel):
    branch_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)
    counted_quantity: Decimal = Field(ge=0,le=100000,max_digits=14,decimal_places=3)
    reason: str = Field(min_length=3,max_length=500)

class ReservationSettingsIn(BaseModel):
    reservation_hours: int = Field(ge=1,le=168)

