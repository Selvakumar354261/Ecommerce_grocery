import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from .db import database
from .models import Session, User, now

ROLE_ACCESS = {
    'customer': {'permissions':['shop','orders.self'],'workspace_pages':[]},
    'admin': {'permissions':['workspace','branch.switch','dashboard.all','orders.manage','inventory.change','inventory.adjust','counts.approve','transfers.manage','purchases.create','purchases.receive','suppliers.create','sales.return','products.manage','branches.manage','users.manage','customers.view','settings.manage','audit.view','reports.export'],'workspace_pages':['dashboard','shifts','orders','deliveries','inventory','counts','transfers','purchases','sales','products','branches','users','customers','settings','audit']},
    'manager': {'permissions':['workspace','orders.manage','inventory.change','inventory.adjust','counts.approve','transfers.manage','purchases.create','purchases.receive','sales.return','reports.export'],'workspace_pages':['dashboard','pos','shifts','orders','deliveries','inventory','counts','transfers','purchases','sales']},
    'cashier': {'permissions':['workspace'],'workspace_pages':['pos','shifts','inventory','sales']},
    'inventory': {'permissions':['workspace','inventory.change','counts.submit','transfers.manage','purchases.receive'],'workspace_pages':['inventory','counts','transfers','purchases']},
    'delivery': {'permissions':['delivery.mobile'],'workspace_pages':[]},
}

def access_for(user):
    access=ROLE_ACCESS.get(user.role,{'permissions':[],'workspace_pages':[]})
    return {'permissions':list(access['permissions']),'workspace_pages':list(access['workspace_pages'])}

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return f'pbkdf2$600000${salt}${digest}'

def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, digest = stored.split('$')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def create_session(db, user):
    token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
    db.add(Session(token_hash=token_hash(token), user_id=user.id, csrf=csrf, expires_at=now()+timedelta(hours=12)))
    return token, csrf

def current_user(request: Request, db: DBSession = Depends(database)):
    authorization=request.headers.get('authorization','')
    bearer=authorization[7:].strip() if authorization.lower().startswith('bearer ') else ''
    token = bearer or request.cookies.get('grocery_session', '')
    session = db.get(Session, token_hash(token)) if token else None
    if not session or session.expires_at <= now():
        raise HTTPException(401, 'Please sign in to continue.')
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, 'This account is inactive.')
    if not bearer and request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), session.csrf):
            raise HTTPException(403, 'Session validation failed. Refresh and retry.')
    request.state.csrf = session.csrf
    return user

def require(user, roles):
    if user.role not in roles:
        raise HTTPException(403, 'Your account cannot perform this action.')

def scope(user, branch_id, roles=('admin','manager','cashier','inventory')):
    require(user, roles)
    if user.role != 'admin' and user.branch_id != branch_id:
        raise HTTPException(403, 'This branch is outside your assigned access.')
