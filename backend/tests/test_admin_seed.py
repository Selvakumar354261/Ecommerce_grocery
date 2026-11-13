from sqlalchemy import select,func,text
from app.db import SessionLocal,engine
from app.models import Base,User,Branch,Product
from app.seed import main
from app.security import verify_password

def test_admin_only_seed_empty_database_and_repeat(monkeypatch):
    assert engine.url.database=='grocery_test'
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE '+','.join('"'+t+'"' for t in Base.metadata.tables)+' RESTART IDENTITY CASCADE'))
    monkeypatch.setenv('SEED_ADMIN_ONLY','true')
    monkeypatch.setenv('SEED_DEMO','true')
    main();main()
    with SessionLocal() as db:
        users=db.scalars(select(User)).all()
        assert len(users)==1
        assert users[0].email=='admin@test.com' and users[0].role=='admin'
        assert verify_password('1234567890',users[0].password_hash)
        assert db.scalar(select(func.count()).select_from(Branch))==0
        assert db.scalar(select(func.count()).select_from(Product))==0

def test_admin_only_seed_preserves_existing_admin(monkeypatch):
    with SessionLocal() as db:
        existing=db.scalar(select(User).where(User.role=='admin'))
        ident,email,password=existing.id,existing.email,existing.password_hash
    monkeypatch.setenv('SEED_ADMIN_ONLY','true')
    main()
    with SessionLocal() as db:
        admin=db.get(User,ident)
        assert admin.email==email and admin.password_hash==password
        assert db.scalar(select(func.count()).select_from(User).where(User.role=='admin'))==1
