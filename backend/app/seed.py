"""Explicitly enabled local administrator-only seed; no demo business data."""
import os
from sqlalchemy import select
from .db import SessionLocal
from .models import User
from .security import hash_password

def main():
    if os.getenv('SEED_ADMIN_ONLY','false').lower()!='true':
        return
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).where(User.role=='admin').limit(1)):
            print('Administrator already exists; seed skipped. Existing credentials are unchanged.')
            return
        if db.scalar(select(User.id).where(User.email=='admin@test.com')):
            raise SystemExit('Admin seed email is already used by another account. No account changed.')
        db.add(User(name='ADMIN',email='admin@test.com',role='admin',branch_id=None,password_hash=hash_password('1234567890')))
    print('Local test administrator created. Change the test password before real use.')

if __name__=='__main__':
    main()
