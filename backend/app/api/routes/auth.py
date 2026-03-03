from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_access_token(username: str) -> Token:
    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(data={"sub": username}, expires_delta=expires)
    return Token(access_token=token)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Annotated[Session, Depends(get_db)]) -> UserRead:
    username = payload.username.strip()
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists.")

    user = User(username=username, password_hash=get_password_hash(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> Token:
    username = payload.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_access_token(user.username)


@router.post("/token", response_model=Token)
def login_oauth2_form(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    payload = LoginRequest(username=form_data.username, password=form_data.password)
    return login(payload=payload, db=db)


@router.get("/me", response_model=UserRead)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return current_user
