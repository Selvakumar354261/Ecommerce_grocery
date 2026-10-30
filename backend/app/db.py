import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://grocery:grocery@db/grocery')
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=10)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def database():
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

