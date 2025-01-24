import os
import jwt
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated
from passlib.context import CryptContext
from fastapi import APIRouter, Body, Depends, Query, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from app.db import get_session
from app.user.model import User

from pydantic import BaseModel, Field

ACCESS_TOKEN_EXPIRE_MINUTES = os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"]
SECRET = os.environ["SECRET"]
ALGORITHM = "HS256"

class UserModel(BaseModel):
    password: str = Field(min_length=8)
    name: str = Field(min_length=4, max_length=20)

class Token(BaseModel):
    access_token: str
    token_type: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()
security = HTTPBearer()

SessionDep = Annotated[Session, Depends(get_session)]

async def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

async def check_user_password(user: UserModel, session: SessionDep):
    statement = select(User).where(User.name == user.name)
    db_user = session.exec(statement).first()

    if not db_user:
        return False
    if not await verify_password(user.password, db_user.password):
        return False
    return db_user

async def check_jwt(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return payload
    except (jwt.exceptions.InvalidSignatureError, jwt.exceptions.ExpiredSignatureError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid token",
        ) from exc

@router.post("/singin", tags=["users"])
async def register(user: Annotated[UserModel, Body()], session: SessionDep):
    db_user = User(
        password=pwd_context.hash(user.password),
        name=user.name
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return {
        "password": db_user.password,
        "name": db_user.name
    }

@router.get("/login", tags=["users"])
async def login(user: Annotated[UserModel, Query()], session: SessionDep):
    db_user = await check_user_password(user, session)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    minutes = float(ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token_expires = timedelta(minutes=minutes)
    access_token = await create_access_token(
        data={"sub": user.name, "id": db_user.id}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")
