from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
import httpx
from sqlalchemy.orm import Session
from datetime import timedelta

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.services import auth as auth_service
from app.models.user import UserCreate, UserLogin, UserOut
from app.database import get_db
from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
    ALGORITHM,
    COOKIE_DOMAIN,
    COOKIE_SECURE,
    COOKIE_SAMESITE,
    TURNSTILE_SECRET_KEY,
    TURNSTILE_ENABLED,
)

router = APIRouter()

def verify_turnstile(token: str | None, request: Request) -> None:
    if not TURNSTILE_ENABLED:
        return
    if not TURNSTILE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="TURNSTILE_SECRET_KEY is not set")
    if not token:
        raise HTTPException(status_code=400, detail="Missing bot verification token")

    payload = {
        "secret": TURNSTILE_SECRET_KEY,
        "response": token,
        "remoteip": request.client.host if request.client else None,
    }
    try:
        resp = httpx.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Bot verification failed: {exc}")

    if not data.get("success"):
        raise HTTPException(status_code=400, detail="Bot verification failed")

@router.post("/signup", response_model=UserOut)
def signup(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    verify_turnstile(user_data.turnstile_token, request)
    existing = auth_service.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = auth_service.get_password_hash(user_data.password)
    new_user = auth_service.models.User(email=user_data.email, hashed_pw=hashed_pw)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=dict)
def login(
    user_data: UserLogin,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticate user, then:
      1) Return a short‐lived access token in the JSON response body.
      2) Set a long‐lived refresh token as an httpOnly cookie.
    """
    verify_turnstile(user_data.turnstile_token, request)
    user = auth_service.authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 1) Create access token
    access_token = auth_service.create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    # 2) Create refresh token
    refresh_token = auth_service.create_refresh_token(
        data={"sub": user.email},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    # 3) Set refresh token as an httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return {"access_token": access_token, "token_type": "bearer"}


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@router.post("/refresh", response_model=dict)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Read the refresh_token from the httpOnly cookie, verify it,
    then issue a new access token (and optionally rotate the refresh token).
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    # 1) Decode/verify the refresh token
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise JWTError("No subject in token")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # 2) Ensure the user is still valid (e.g., not deleted or disabled)
    user = auth_service.get_user_by_email(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # 3) Issue a new access token
    new_access_token = auth_service.create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    # 4) Refresh cookie (optional rotation)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return {"access_token": new_access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def read_users_me(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    Standard “get me” endpoint. Reads the Authorization: Bearer <access_token>
    header, decodes it, and returns the current user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = auth_service.get_user_by_email(db, email)
    if user is None:
        raise credentials_exception

    return user
