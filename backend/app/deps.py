from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.service import AuthUser, current_user_from_request, require_admin, require_csrf
from app.config import get_settings
from app.database import get_db


def get_current_user(request: Request, db: Session = Depends(get_db)) -> AuthUser:
    return current_user_from_request(db, request, get_settings())


def get_active_user(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not user.is_active:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


def get_admin_user(request: Request, user: AuthUser = Depends(get_active_user)) -> AuthUser:
    require_csrf(request)
    require_admin(user)
    return user


def get_admin_user_readonly(user: AuthUser = Depends(get_active_user)) -> AuthUser:
    require_admin(user)
    return user
