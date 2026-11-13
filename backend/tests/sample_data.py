import os
from decimal import Decimal
from sqlalchemy import select
from app.db import SessionLocal, engine
from app.models import Branch, User, Product, Variant, Stock, Movement, Supplier
from app.security import hash_password

def main():
    assert engine.url.database == 'grocery_test', 'Sample data is restricted to the isolated test database.'
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).limit(1)):return
        places=[('Central Market','Demo: Gandhi Road, Erode',11.3410,77.7172),('Garden Road','Demo: Perundurai Road, Erode',11.3470,77.6990),('Riverside','Demo: Bhavani Road, Erode',11.3650,77.7210),('South Square','Demo: Moolapalayam, Erode',11.3140,77.7230)]
        branches=[]
        for name,address,lat,lon in places:
            b=Branch(name=name,address=address,latitude=lat,longitude=lon,radius_km=12,delivery_fee=30,hours='09:00–21:00')
            db.add(b);db.flush();branches.append(b)
        password=hash_password(os.environ.get('DEMO_PASSWORD','DemoGrocery!2026'))
        for name,email,role,branch in [('Store Owner','admin@gmail.com','admin',None),('Branch Manager','manager@gmail.com','manager',branches[0].id),('Cashier','cashier@gmail.com','cashier',branches[0].id),('Stock Team','inventory@gmail.com','inventory',branches[0].id),('Demo Customer','customer@gmail.com','customer',None)]:
            db.add(User(name=name,email=email,role=role,branch_id=branch,password_hash=password))
        products=[
            ('Heritage Ponni Rice','Rice','Everyday rice with a soft texture and a naturally clean finish.','sage',[('RICE-1KG','1 kg sealed pack','pack',78,1,1),('RICE-5KG','5 kg sealed bag','pack',375,1,1),('RICE-LOOSE','Loose · price per kg','kg',74,.25,.25)]),
            ('Cold Pressed Groundnut Oil','Oil','A kitchen staple with a rich aroma.','gold',[('OIL-1L','1 litre bottle','pack',245,1,1),('OIL-LOOSE','Loose · price per litre','litre',230,.5,.5)]),
            ('Whole Almonds','Nuts','Carefully selected almonds for snacks and everyday recipes.','rose',[('ALM-250','250 g sealed pouch','pack',225,1,1),('ALM-LOOSE','Loose · price per kg','kg',840,.1,.05)]),
            ('Premium Cashews','Nuts','Whole cashews with a creamy texture.','clay',[('CAS-250','250 g sealed pouch','pack',240,1,1),('CAS-LOOSE','Loose · price per kg','kg',920,.1,.05)]),
            ('Toor Dal','Essentials','An everyday pantry essential, carefully cleaned and packed.','gold',[('DAL-1KG','1 kg sealed pack','pack',165,1,1)]),
            ('Organic Jaggery','Essentials','Traditional sweetness for your favourite recipes.','clay',[('JAG-500','500 g sealed pack','pack',62,1,1)]),
            ('Extra Virgin Coconut Oil','Oil','Pure coconut oil for a well-stocked kitchen.','sage',[('COCO-500','500 ml bottle','pack',195,1,1)]),
            ('Raw Peanuts','Nuts','Versatile peanuts for roasting, cooking, and snacking.','rose',[('PEA-LOOSE','Loose · price per kg','kg',160,.25,.25)]),
        ]
        for index,(name,cat,desc,tone,variants) in enumerate(products):
            p=Product(name=name,category=cat,description=desc,tone=tone);db.add(p);db.flush()
            for sku,label,unit,price,minimum,step in variants:
                v=Variant(product_id=p.id,sku=sku,label=label,unit=unit,price=price,min_qty=Decimal(str(minimum)),step=Decimal(str(step)),max_qty=100)
                db.add(v);db.flush()
                for j,b in enumerate(branches):
                    qty=Decimal(40+j*10-index*2)
                    if j==2 and sku=='CAS-250':qty=Decimal(0)
                    if j==0 and sku=='JAG-500':qty=Decimal(3)
                    db.add(Stock(branch_id=b.id,variant_id=v.id,on_hand=qty,reserved=0,damaged=0,reorder=5))
                    db.add(Movement(branch_id=b.id,variant_id=v.id,delta=qty,kind='opening',reference='demo-seed',reason='Demonstration opening balance'))
        db.add(Supplier(name='Demo Grain & Pantry Supply',phone='0000000000',address='Demonstration supplier'))
    print('Demo catalogue and accounts created. See README for local credentials.')
