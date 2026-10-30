"""Interactive first administrator creation for an empty non-demo installation."""
import getpass
from sqlalchemy import select
from .db import SessionLocal
from .models import User
from .security import hash_password

def main():
    name=input('Administrator name: ').strip()
    email=input('Administrator email: ').strip().lower()
    password=getpass.getpass('Password (at least 12 characters): ')
    confirmation=getpass.getpass('Repeat password: ')
    if len(name)<2 or '@' not in email or len(password)<12 or password!=confirmation:
        raise SystemExit('Invalid entries or passwords did not match. No account created.')
    with SessionLocal.begin() as db:
        if db.scalar(select(User).where(User.role=='admin')):
            raise SystemExit('An administrator already exists. Bootstrap is only for the first administrator.')
        db.add(User(name=name,email=email,password_hash=hash_password(password),role='admin'))
    print('Administrator created. Sign in and add your first branch.')

if __name__=='__main__':main()

