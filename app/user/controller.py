from typing import Annotated
from passlib.context import CryptContext
from fastapi import APIRouter, Body, Depends
from sqlmodel import Session #, Field, SQLModel
from app.db import get_session
from app.user.model import User

from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    password: str = Field(min_length=8)
    name: str = Field(min_length=4, max_length=20)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]

@router.get("/singin", tags=["users"])
async def register(user: Annotated[UserCreate, Body()], session: SessionDep):
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
