from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import mailer
from app.config import settings
from app.database import get_db, utcnow
from app.deps import get_current_user, require_roles
from app.models import PasswordResetToken, Role, User
from app.schemas import ForgotIn, LoginIn, ResetIn, SignupIn, StaffIn, TokenOut
from app.security import (create_access_token, hash_password, hash_token, new_reset_token,
                          verify_password)
from app.serializers import user_out

router = APIRouter(tags=["auth"])


def _by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if _by_email(db, body.email):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=body.email.lower(), full_name=body.full_name,
                password_hash=hash_password(body.password), role=Role.customer)
    db.add(user)
    db.commit()
    return user_out(user)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = _by_email(db, body.email)
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id, user.role))


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/auth/forgot-password", status_code=202)
def forgot_password(body: ForgotIn, db: Session = Depends(get_db)):
    # Same response whether or not the email exists, so the endpoint cannot be used to enumerate accounts.
    user = _by_email(db, body.email)
    if user is not None and user.is_active:
        raw, digest = new_reset_token()
        db.add(PasswordResetToken(user_id=user.id, token_hash=digest,
                                  expires_at=utcnow() + timedelta(minutes=settings.reset_token_minutes)))
        db.commit()
        link = f"{settings.frontend_url}/reset-password?token={raw}"
        mailer.send_email(user.email, "Reset your password",
                          f"Open this link within {settings.reset_token_minutes} minutes to reset your password:\n{link}")
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/auth/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(body.token)))
    if token is None or token.used_at is not None or token.expires_at < utcnow():
        raise HTTPException(400, "This reset link is invalid or has expired")
    user = db.get(User, token.user_id)
    user.password_hash = hash_password(body.new_password)
    # Single use: burn every outstanding reset token for this user.
    db.execute(update(PasswordResetToken)
               .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
               .values(used_at=utcnow()))
    db.commit()
    return {"message": "Password updated. You can now log in."}


@router.post("/admin/staff", status_code=201)
def create_staff(body: StaffIn, _admin: User = Depends(require_roles(Role.admin)),
                 db: Session = Depends(get_db)):
    if _by_email(db, body.email):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=body.email.lower(), full_name=body.full_name,
                password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    return user_out(user)


@router.get("/admin/customers")
def list_customers(_user: User = Depends(require_roles(Role.admin, Role.staff)),
                   db: Session = Depends(get_db)):
    """Customer directory used by the console's dropdowns (capped at 500 rows)."""
    rows = db.scalars(select(User).where(User.role == Role.customer).order_by(User.id).limit(500)).all()
    return [user_out(u) for u in rows]
